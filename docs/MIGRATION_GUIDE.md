# MIGRATION_GUIDE.md — 迁移指南

> 版本: V11.5 (SkillOS Convergence Refactor)
> 日期: 2026-06-02

---

## 1. Tool Profile 迁移

### 旧版行为
- 所有 55 个工具始终暴露

### 新版行为
- 默认 `minimal` profile，只暴露 10 个核心工具
- 通过环境变量 `STABLE_AGENT_TOOL_PROFILE` 控制

### 如何继续使用旧版
```bash
export STABLE_AGENT_TOOL_PROFILE=full
```

### 如何使用新版
```bash
export STABLE_AGENT_TOOL_PROFILE=minimal  # 默认
```

---

## 2. SkillRepo 迁移

### 旧版
- 单一 `best_skill.md` 文件
- 通过 `stableagent.skillopt.*` 工具管理

### 新版
- 文件 + SQLite 双层存储
- `.skills/` 目录结构
- 通过 `stable_agent/skills/repository.py` 管理

### 迁移步骤
1. 旧版 `best_skill.md` 仍可通过 `stableagent.skillopt.export_best` 导出
2. 新版使用 `stableagent skill list` 查看
3. 新版 candidate 不会直接 promoted，需要验证

---

## 3. Observer Replay 迁移

### 旧版
- RunStore 纯内存，页面刷新后事件丢失
- Observer 显示 0%

### 新版
- RunStore 内存 + SQLite 双层
- 页面刷新后从 SQLite 回放
- Observer 正确显示历史进度

### 无需迁移
- 自动生效，无需手动操作

---

## 4. CLI 命令迁移

### 新增命令
```bash
stableagent doctor              # 综合健康检查
stableagent skill list          # 列出技能
stableagent skill show <id>     # 显示技能详情
stableagent skill validate <id> # 验证技能
stableagent skill promote <id>  # 晋升技能
```

### 旧命令保留
```bash
stableagent capsule status      # 胶囊状态
stableagent memory health       # 记忆健康
stableagent task run -t "..."   # 执行任务
```

---

## 5. Claude Code 连接

### 生成 .mcp.json
```bash
bash scripts/connect_claude_code.sh
```

### 手动配置
```json
{
  "mcpServers": {
    "stableagent": {
      "type": "stdio",
      "command": "/path/to/.venv/bin/python",
      "args": ["-m", "stable_agent.mcp_stdio", "--profile", "minimal"],
      "env": {
        "PYTHONPATH": "/path/to/project",
        "STABLE_AGENT_TOOL_PROFILE": "minimal"
      }
    }
  }
}
```

---

## 6. 回滚到旧行为

### 完全回滚
```bash
git checkout main
```

### 部分回滚
```bash
# 只回滚 Tool Profile
export STABLE_AGENT_TOOL_PROFILE=full

# 只回滚 Observer (无操作，自动兼容)
```
