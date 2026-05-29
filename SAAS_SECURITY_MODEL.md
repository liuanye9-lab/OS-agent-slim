# SaaS Security Model

> StableAgent Cloud 安全模型
> 版本: v2.2

## 认证方式

### JWT Token
- 算法: HMAC-SHA256
- TTL: 24 小时
- 端点: POST /api/auth/register, POST /api/auth/login, POST /api/auth/verify

### API Key
- 格式: `sk_` 前缀 + 随机字符串
- 哈希: SHA256 (仅存哈希，不存明文)
- 一次性显示: 创建时返回完整 key，之后不可检索
- 状态: active / revoked

## 运行模式

### Local Mode (`STABLE_AGENT_MODE=local`)
- 匿名用户: user_id="anonymous"
- 所有权限检查放行
- 适用于本地开发和测试

### SaaS Mode (`STABLE_AGENT_MODE=saas`)
- 强制 JWT 或 API Key 认证
- 401: 未认证
- 403: 权限不足
- 所有操作记录审计日志

## 权限矩阵

| 操作 | Owner | Admin | Developer | Reviewer | Viewer |
|------|-------|-------|-----------|----------|--------|
| 创建工作空间 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 创建项目 | ✅ | ✅ | ✅ | ❌ | ❌ |
| 创建 Run | ✅ | ✅ | ✅ | ❌ | ❌ |
| 审核 Skill Patch | ✅ | ✅ | ❌ | ✅ | ❌ |
| 查看 Dashboard | ✅ | ✅ | ✅ | ✅ | ✅ |
| 创建 API Key | ✅ | ✅ | ❌ | ❌ | ❌ |
| 查看审计日志 | ✅ | ✅ | ❌ | ❌ | ❌ |

## 高风险操作审批

| 工具 | 风险等级 | 审批流程 |
|------|----------|----------|
| stableagent.approval.respond | high | 创建 PendingToolCall → 用户 approve/reject |
| stableagent.skill.export_best | high | 必须先通过 Validation Gate + Human Review |
| stableagent.skill.review | high | 人工审核 |
| stableagent.apikey.create | high | 需要审批 |
| stableagent.apikey.revoke | high | 需要审批 |

## 审计日志

13 种事件类型，不可变存储:
- api_key_created / api_key_revoked
- mcp_tool_called
- high_risk_tool_blocked
- approval_requested / approval_approved / approval_rejected
- skill_patch_created / skill_patch_validated / skill_patch_reviewed
- best_skill_exported
- project_deleted
- member_invited
