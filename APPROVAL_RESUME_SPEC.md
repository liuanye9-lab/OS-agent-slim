# Approval Resume Specification

> 高风险工具审批恢复规范
> 版本: v2.2

## 概述

高风险 MCP 工具调用被硬阻断后，通过审批恢复机制执行。核心闭环:

```
高风险工具调用
    ↓
ToolRouter.route() → risk_level == "high"
    ↓
创建 PendingToolCall → 保存到 PendingToolStore
    ↓
发布 approval.required + tool.blocked.waiting_approval
    ↓
返回 waiting_approval (不执行 handler)
    ↓
用户 approve → ApprovalResumeService.approve_and_resume()
    ├── → ToolRouter.route_resume() → 执行 handler → 返回真实结果
用户 reject → ApprovalResumeService.reject()
    └── → 标记 rejected → 永不执行
```

## 关键限制

- ❌ 不允许自动恢复（必须人工 approve）
- ❌ 不允许绕过审批（risk_level=high 直接返回，不执行 handler）
- ❌ 不允许重复执行（已 approved/rejected 的审批不可再次操作）
- ❌ 不允许超时自动通过

## 数据结构

```python
@dataclass
class PendingToolCall:
    approval_id: str
    run_id: str
    tool_name: str
    args: dict
    workspace_id: str
    project_id: str
    created_at: float
    status: str  # waiting_approval | approved | rejected
```

## 存储

- 内存: dict[approval_id, PendingToolCall] (快速查询)
- SQLite: approval_pending_calls 表 (持久化)
- 索引: idx_apc_run_id ON approval_pending_calls(run_id)

## 实现位置

- `stable_agent/approval/pending_tool_store.py` — 存储层
- `stable_agent/approval/approval_resume_service.py` — 恢复服务
- `stable_agent/gateway/tool_router.py` — 阻断 + 恢复入口
- MCP Tool: `stableagent.approval.respond` — 审批响应
