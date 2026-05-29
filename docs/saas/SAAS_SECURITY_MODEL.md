# SAAS_SECURITY_MODEL.md

StableAgent Cloud 安全架构与威胁模型。

---

## 1. 认证

### 双通道
| 通道 | 格式 | 用途 |
|------|------|------|
| JWT Token | `Authorization: Bearer <token>` | Web Dashboard 登录 |
| API Key | `X-API-Key: sk_<hex>` | MCP 工具调用 |

### JWT
- 算法: HMAC-SHA256
- TTL: 24 小时
- Payload: `{sub, email, name, iat, exp}`
- 环境变量: `JWT_SECRET`

### API Key
- 前缀: `sk_` + 32 字节 hex
- 存储: SHA256 hash（不存明文）
- 生命周期: create → active → revoke
- 一次性显示（创建后不可再次查看）

---

## 2. 权限

### RBAC 5 级
| 角色 | 查看 | 创建Run | 导出Skill | 审核 | 管理成员 |
|------|------|--------|----------|------|---------|
| Owner | ✅ | ✅ | ✅ | ✅ | ✅ |
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ |
| Developer | ✅ | ✅ | ❌ | ❌ | ❌ |
| Reviewer | ✅ | ❌ | ❌ | ✅ | ❌ |
| Viewer | ✅ | ❌ | ❌ | ❌ | ❌ |

### 模式切换
- `STABLE_AGENT_MODE=local`: 全部放行（开发环境）
- `STABLE_AGENT_MODE=saas`: 强制 JWT/API Key 校验

---

## 3. 审批

### 风险等级
| 等级 | 行为 | 示例工具 |
|------|------|---------|
| `low` | 直接执行 | `run.get`, `usage.get` |
| `medium` | 执行 + audit log | `project.create`, `skill.patch_propose` |
| `high` | **硬阻断 → 等待审批** | `skill.export_best`, `skill.review` |
| `forbidden` | 直接拒绝 | （系统保留） |

### 审批流程
```
high risk tool called
  → ToolRouter blocks execution
  → approval.required event published
  → waiting_approval returned
  → Human Review panel shows pending
  → Reviewer approves/rejects
  → best_skill.md exported (or rejected)
```

---

## 4. 审计

### 审计事件类型
`workspace_created`, `project_created`, `run_created`, `run_completed`,
`api_key_created`, `api_key_revoked`, `member_invited`, `member_role_changed`,
`skill_patch_proposed`, `skill_patch_approved`, `skill_patch_rejected`,
`skill_exported`, `mcp_tool_called`

### 审计字段
`{id, workspace_id, event_type, actor_id, target_type, target_id, details, created_at}`

---

## 5. 速率限制

| 套餐 | QPM | 滑动窗口 |
|------|-----|---------|
| Free | 10 | 60s |
| Pro | 60 | 60s |
| Team | 300 | 60s |
| Enterprise | ∞ | — |

---

## 6. 数据保护

- **密码**: SHA256 + salt（不存明文）
- **API Key**: SHA256 hash（不存明文，仅创建时显示一次）
- **User task content**: 不写入 skill（隐私隔离）
- **Skill content**: 不包含原始用户输入
- **审计日志**: 不可篡改（append-only）
- **数据库**: WAL 模式（崩溃可恢复）

---

## 7. 威胁模型

| 威胁 | 缓解 |
|------|------|
| 未授权 access | JWT + API Key 双通道认证 |
| 权限提升 | RBAC 5 级矩阵 |
| 高风险操作绕过 | Approval hard-block |
| API 滥用 | Rate limiter per key |
| 审计绕过 | 所有写操作 → audit log |
| SQL 注入 | 参数化查询 (sqlite3 `?` placeholder) |
| XSS | FastAPI auto-escaping + CSP headers |
| 隐私泄露 | User task content never written to skill |
| Token 劫持 | JWT 24h TTL + revocable API Key |
