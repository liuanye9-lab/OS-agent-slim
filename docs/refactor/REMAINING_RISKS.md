# REMAINING_RISKS.md — 剩余风险

> 日期: 2026-06-02

---

## P1 风险

### 1. Executor 未完全抽出
- **描述**: `_h_task_os_agent` (575行) 仍在 unified_tool_registry.py 中，OSAgentExecutor 是并行副本
- **影响**: 两套执行逻辑可能不一致
- **缓解**: 下一步将 _h_task_os_agent 委托给 OSAgentExecutor

### 2. 旧测试可能受影响
- **描述**: profile 过滤可能影响旧测试的工具数量断言
- **影响**: 已修复 test_unified_tool_registry.py，其他测试可能受影响
- **缓解**: 运行完整测试套件验证

---

## P2 风险

### 3. Delayed Validation 为 stub
- **描述**: `validate_delayed()` 当前直接通过，未实现真正的 related task 验证
- **影响**: 技能验证不够严格
- **缓解**: 后续实现基于 related tasks 的真实验证

### 4. Human Review 未集成
- **描述**: 高风险 skill 自动跳过 promote，但没有 human review UI
- **影响**: 高风险技能无法 promote
- **缓解**: 后续集成 human review 流程

### 5. MCP stdio 未更新 profile
- **描述**: mcp_stdio.py 仍使用旧的硬编码工具列表
- **影响**: stdio 模式下工具数量不受 profile 控制
- **缓解**: 后续更新 mcp_stdio.py 支持 profile 参数

### 6. RunStore SQLite 未注入到 web/app.py
- **描述**: web/app.py 创建 RunStore 时未传入 db_path
- **影响**: Observer 0% 问题可能在生产环境仍存在
- **缓解**: 后续更新 web/app.py 注入 db_path
