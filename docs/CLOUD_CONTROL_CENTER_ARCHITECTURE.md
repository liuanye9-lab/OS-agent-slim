# OpenClaw Cloud Control Center 架构文档

## 设计哲学

OpenClaw Control Center 像机场塔台:

- **云端不亲自开飞机** — 不执行实际 coding/shell 任务
- **云端负责调度、记录、分配、观察** — 管理任务队列和 Worker
- **本地两台电脑才是执行节点** — Worker 拉取任务并执行
- **Dashboard 是塔台雷达屏幕** — 可视化系统状态
- **Agent Capsule 是飞行规则** — 记忆、偏好、历史经验

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                 OpenClaw Control Center              │
│                 (阿里云 ECS 2核2G)                    │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ MCP GW   │  │ Cloud API│  │ Slim Dashboard   │  │
│  │ /mcp/    │  │ /api/    │  │ /slim            │  │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│       │              │                 │             │
│  ┌────┴──────────────┴─────────────────┴─────────┐  │
│  │            Control Center Core                 │  │
│  │  ┌───────────┐ ┌──────────┐ ┌──────────────┐  │  │
│  │  │Task Queue │ │Scheduler │ │Worker Registry│  │  │
│  │  │(SQLite)   │ │          │ │(SQLite)       │  │  │
│  │  └───────────┘ └──────────┘ └──────────────┘  │  │
│  │  ┌───────────┐ ┌──────────────────────────┐   │  │
│  │  │Event Store│ │ Agent Capsule            │   │  │
│  │  │(SQLite)   │ │ (memory/bad_cases/token) │   │  │
│  │  └───────────┘ └──────────────────────────┘   │  │
│  └────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP API
        ┌─────────────┴─────────────┐
        │                           │
┌───────┴───────┐         ┌────────┴────────┐
│  Worker A     │         │  Worker B       │
│  MacBook Pro  │         │  Desktop PC     │
│  (coding,     │         │  (coding,       │
│   shell)      │         │   browser,      │
│               │         │   shell)        │
└───────────────┘         └─────────────────┘
```

## 核心组件

### 1. ControlCenter (`cloud/control_center.py`)

中枢调度器，协调所有组件:

- **submit_task()** — 接收任务
- **register_worker()** — 注册 Worker
- **worker_heartbeat()** — 心跳处理
- **task_started/completed/failed()** — 生命周期管理
- **get_next_task()** — 为 Worker 分配任务

### 2. TaskQueue (`cloud/task_queue.py`)

SQLite 任务队列:

- 任务状态: queued → assigned → running → completed/failed/cancelled
- 支持优先级排序
- 每任务日志 (最多 200 条)

### 3. WorkerRegistry (`cloud/worker_registry.py`)

Worker 管理:

- 注册/心跳/状态管理
- 超时自动 offline (60 秒)
- 能力匹配

### 4. Scheduler (`cloud/scheduler.py`)

简单调度器:

- 指定 Worker 优先
- 在线 + 空闲 + 最近心跳
- 无可用 Worker → 保持 queued

### 5. EventStore (`cloud/event_store.py`)

事件存储:

- 最多保留 1000 条事件
- 支持按 task_id / run_id / event_type 查询

### 6. Security (`cloud/security.py`)

可选 Token 认证:

- `STABLEAGENT_CLOUD_TOKEN` 环境变量
- Bearer Token 验证
- Dashboard 页面可选跳过

## 数据存储

```
.stableagent-capsule/
├── cloud/
│   └── cloud.sqlite          # tasks + workers + events
├── profile/
│   └── expressions.json      # 表达习惯规则
├── memory/                   # 记忆条目
├── bad_cases.jsonl           # 失败案例
└── manifest.json             # Capsule 元信息
```

## API 端点

### Health
- `GET /api/cloud/health` — 系统健康检查

### Workers
- `POST /api/workers/register` — 注册 Worker
- `GET /api/workers` — 列出 Workers
- `POST /api/workers/{id}/heartbeat` — 心跳
- `GET /api/workers/{id}/next-task` — 拉取任务
- `POST /api/workers/{id}/task/{task_id}/started` — 任务开始
- `POST /api/workers/{id}/task/{task_id}/log` — 日志回传
- `POST /api/workers/{id}/task/{task_id}/completed` — 任务完成
- `POST /api/workers/{id}/task/{task_id}/failed` — 任务失败

### Tasks
- `POST /api/tasks` — 创建任务
- `GET /api/tasks` — 列出任务
- `GET /api/tasks/{id}` — 任务详情
- `POST /api/tasks/{id}/cancel` — 取消任务

### Dashboard
- `GET /slim` — Dashboard 页面
- `GET /api/slim/status` — 聚合状态数据
- `GET /api/slim/capsule` — Capsule 摘要

### MCP
- `POST /mcp/` — JSON-RPC 2.0 端点
- `GET /mcp/tools` — 工具列表
- `GET /mcp/health` — MCP 健康检查

## MCP 工具 (Slim 模式)

### 核心工具
- `stableagent.task.os_agent` — 提交任务到 Control Center
- `stableagent.feedback.remember` — 记住
- `stableagent.feedback.dont_do_this_again` — 下次别这样
- `stableagent.feedback.correct_and_remember` — 纠正并记住

### Cloud 工具
- `stableagent.cloud.worker.list` — 列出 Workers
- `stableagent.cloud.worker.status` — Worker 状态
- `stableagent.cloud.task.create` — 创建任务
- `stableagent.cloud.task.list` — 列出任务
- `stableagent.cloud.task.get` — 任务详情
- `stableagent.cloud.task.cancel` — 取消任务

### Capsule 工具
- `stableagent.capsule.status` — 胶囊状态
- `stableagent.memory.health` — 记忆健康
- `stableagent.token.summary` — Token 摘要

## 资源优化

| 配置 | 值 | 说明 |
|------|-----|------|
| Uvicorn workers | 1 | 单进程 |
| MemoryMax | 1200M | systemd 限制 |
| 最大事件数 | 1000 | 自动裁剪 |
| 每任务日志 | 200 条 | 自动裁剪 |
| Dashboard 轮询 | 3 秒 | 不用 WebSocket |
| Worker 超时 | 60 秒 | 自动 offline |

## 与 Full 模式的区别

| 功能 | Slim | Full |
|------|------|------|
| SaaS 多租户 | ❌ 禁用 | ✅ |
| Billing | ❌ 禁用 | ✅ |
| SkillOpt | ❌ 禁用 | ✅ |
| Canvas 动画 | ❌ 禁用 | ✅ |
| WebSocket Dashboard | ❌ 用轮询 | ✅ |
| Effectiveness Dashboard | ❌ 禁用 | ✅ |
| 本地 LLM 推理 | ❌ 禁用 | ✅ |
| MCP Gateway | ✅ | ✅ |
| CLI | ✅ | ✅ |
| Agent Capsule | ✅ | ✅ |
| Feedback Loop | ✅ | ✅ |
| Task Queue | ✅ (新增) | ❌ |
| Worker Management | ✅ (新增) | ❌ |
