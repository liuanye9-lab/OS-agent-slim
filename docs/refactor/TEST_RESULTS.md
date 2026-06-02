# TEST_RESULTS.md — 测试结果

> 测试日期: 2026-06-02
> 测试环境: macOS, Python 3.9.6/3.13.12

---

## 1. py_compile 结果

| 文件 | 结果 |
|------|------|
| stable_agent/gateway/tool_profiles.py | ✅ OK |
| stable_agent/core/__init__.py | ✅ OK |
| stable_agent/core/models.py | ✅ OK |
| stable_agent/core/executor.py | ✅ OK |
| stable_agent/core/curator.py | ✅ OK |
| stable_agent/core/validator.py | ✅ OK |
| stable_agent/core/contracts.py | ✅ OK |
| stable_agent/skills/__init__.py | ✅ OK |
| stable_agent/skills/models.py | ✅ OK |
| stable_agent/skills/markdown.py | ✅ OK |
| stable_agent/skills/repository.py | ✅ OK |
| stable_agent/skills/index_store.py | ✅ OK |
| stable_agent/skills/lifecycle.py | ✅ OK |
| stable_agent/observation/run_store.py | ✅ OK |
| stable_agent/cli.py | ✅ OK |
| stable_agent/gateway/unified_tool_registry.py | ✅ OK |

**总计: 16/16 通过**

---

## 2. pytest 结果

### 2.1 新增测试 (70 个)

| 测试文件 | 测试数 | 通过 | 失败 |
|----------|--------|------|------|
| test_tool_profiles.py | 15 | 15 | 0 |
| test_skill_repo_v2.py | 14 | 14 | 0 |
| test_curator_policy.py | 12 | 12 | 0 |
| test_promotion_gate.py | 13 | 13 | 0 |
| test_dry_run_learning_safety.py | 4 | 4 | 0 |
| test_observer_replay_api.py | 12 | 12 | 0 |

**新增测试: 70/70 通过**

### 2.2 已有测试 (76 个)

| 测试文件 | 测试数 | 通过 | 失败 |
|----------|--------|------|------|
| test_unified_tool_registry.py | 6 | 6 | 0 |
| test_tool_schemas.py | 41 | 41 | 0 |
| test_p0_core.py | 29 | 29 | 0 |

**已有测试: 76/76 通过**

### 2.3 总计

**总计: 146/146 通过**

---

## 3. check_closed_loop 结果

28 项结构检查全部通过。

---

## 4. 待运行测试

| 测试 | 状态 | 说明 |
|------|------|------|
| integration_test.sh | ⏳ | 需要运行中的服务器 |
| quickstart.sh | ⏳ | 需要 Python 环境 |
| connect_claude_code.sh | ⏳ | 需要 Claude Code 环境 |
