# 03_RISK_AND_ROLLBACK.md

> 创建时间: 2026-06-02

---

## 风险矩阵

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 重构破坏 os_agent 正常路径 | P0 | 中 | 每阶段运行 integration_test + check_closed_loop |
| Tool Profile 导致旧客户端无法调用 | P1 | 低 | full profile 保留所有旧工具 |
| SkillRepo v2 与现有 skillopt 冲突 | P1 | 中 | 新增独立目录，不修改现有 skillopt |
| Observer replay 修复引入新 bug | P2 | 低 | 先 API 回放再 WebSocket，渐进式修改 |
| CLI 入口与现有 cli.py 冲突 | P2 | 低 | 扩展现有 cli.py，不重写 |
| 测试覆盖不足导致回归 | P1 | 中 | 新增 13 个测试文件覆盖所有新模块 |

---

## 回滚策略

### 每阶段回滚

```bash
# 1. 保存当前变更
git stash save "Phase N: <描述>"

# 2. 回到上一个稳定提交
git checkout <上一个稳定 commit>

# 3. 验证基线仍然正常
python tools/check_closed_loop.py

# 4. 如果需要恢复变更
git stash pop
```

### 全局回滚

```bash
# 1. 回到重构前基线
git checkout main

# 2. 验证基线
python tools/check_closed_loop.py
bash scripts/integration_test.sh

# 3. 删除重构分支
git branch -D refactor/skillos-convergence
```

---

## 验证检查点

每个 Phase 完成后必须通过：

1. `python -m py_compile stable_agent/gateway/unified_tool_registry.py`
2. `python tools/check_closed_loop.py`
3. `python -m pytest tests/ -q` (至少不新增失败)
4. `bash scripts/integration_test.sh` (需要服务器运行)

Phase 9 最终验收额外需要：

5. `bash scripts/quickstart.sh`
6. `bash scripts/connect_claude_code.sh`
7. 13 个新增测试文件全部通过
