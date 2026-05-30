"""StableAgent OS 编排器 — 整合所有模块完成端到端任务。

本模块是 StableAgent OS 的"大脑皮层"，将之前所有模块串联成完整
可运行的系统。通过 StableAgentOrchestrator 整合决策引擎、预算管理、
记忆路由、RAG、工作流引擎、事件总线、知识图谱、版本控制和沙箱，
对外提供统一的 process_task 接口。

V3 升级：
- 整合所有 V3 新模块：storage, token_meter, context_pack,
  retrieval_policy, plain_language, security_policy, approval,
  llm_client, eval_dataset, mcp_tools
- process_task 升级为完整 17 步流程
- 新增 start_run, resume_run, get_run_status, get_run_trace,
  build_context_pack_api 方法

模块职责：
- 实例化并连接所有核心模块
- 端到端任务处理流程
- 系统状态摘要查询
- 完整的演示入口 run_demo()
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

from stable_agent.models import (
    ApprovalRequest,
    BadCase,
    ContextPack,
    EvaluationResult,
    Event,
    MemoryItem,
    RunRecord,
    TaskType,
    TokenBudget,
    TraceSpan,
    Workflow,
)
from stable_agent.context_decision_engine import ContextDecisionEngine
from stable_agent.context_budget_manager import ContextBudgetManager
from stable_agent.memory_router import MemoryBank, MemoryRouter
from stable_agent.eval_and_bad_case import BadCaseManager, Evaluator
from stable_agent.workflow_state_machine import WorkflowEngine
from stable_agent.trace_event_bus import EventBus, TraceStorage
from stable_agent.rag_context_pack import RagContextManager
from stable_agent.temporal_knowledge_graph import TemporalKnowledgeGraph
from stable_agent.git_diff_checkpoint import VersionControlManager
from stable_agent.tool_hub import ToolHub
from stable_agent.swe_sandbox import Sandbox

# V3 新增模块
from stable_agent.storage import StableAgentStorage
from stable_agent.token_meter import TokenMeter
from stable_agent.context_pack import ContextTriage, ContextPackBuilder
from stable_agent.retrieval_policy import RetrievalPolicy, RetrievalCritic
from stable_agent.plain_language import PlainLanguageExplainer
from stable_agent.security_policy import SecurityPolicy
from stable_agent.approval import ApprovalManager
from stable_agent.llm_client import MockLLMClient
from stable_agent.eval_dataset import EvalDatasetManager

# V6.0 Self-Improvement Proof Loop
from stable_agent.self_improvement.proof_loop import SelfImprovementProofLoop
from stable_agent.self_improvement.memory_update_candidate import MemoryUpdateStore
from stable_agent.self_improvement.skill_patch_candidate import SkillPatchStore

# V6.1: Temporal Memory + Context Compression
from stable_agent.memory.temporal_memory_bridge import TemporalMemoryBridge
from stable_agent.context.context_compression_guard import ContextCompressionGuard


# ============================================================================
# StableAgentOrchestrator — 系统编排器
# ============================================================================


class StableAgentOrchestrator:
    """StableAgent OS 编排器。

    整合所有核心模块，提供端到端的任务处理能力。负责模块实例化、
    连接和生命周期管理。

    V3 新增：
    - storage: SQLite 持久化存储
    - token_meter: Token 计量器
    - context_triage: 上下文筛选排序压缩
    - context_pack_builder: ContextPack 工厂
    - retrieval_policy: 检索策略
    - retrieval_critic: 检索后二次筛选
    - plain_language: 大白话解释器
    - security_policy: 安全策略
    - approval_manager: 审批管理器
    - llm_client: LLM 客户端
    - eval_dataset_mgr: 评估数据集管理器
    - mcp_tools: MCP 工具注册中心

    Attributes:
        event_bus: 事件发布订阅总线。
        decision_engine: 上下文决策引擎。
        budget_manager: 上下文预算管理器。
        memory_bank: 底层记忆存储。
        memory_router: 高级记忆检索接口。
        evaluator: 模型输出评估器。
        bad_case_manager: 负面案例管理器。
        workflow_engine: 工作流状态机引擎。
        rag_manager: RAG 上下文包管理器。
        knowledge_graph: 时间知识图谱。
        version_control: Git 版本控制管理器。
        tool_hub: 工具注册与调用中心。
        sandbox: 安全沙箱执行环境。
        trace_storage: 事件持久化存储。
    """

    def __init__(self, evaluator: "Evaluator | None" = None, llm_client: "Any | None" = None) -> None:
        """初始化 StableAgentOrchestrator。

        实例化所有核心模块，建立模块间的连接：
        - EventBus 注入 WorkflowEngine
        - EventBus 订阅 TraceStorage 实现自动持久化
        - 预填充示例记忆到 MemoryBank 用于演示
        - V3: 实例化所有新模块并连接

        Args:
            evaluator: 预配置的 Evaluator 实例（可带 LLM 客户端）。
            llm_client: LLM 客户端实例，注入 Evaluator 和 WorkflowEngine。
        """
        # ------------------------------------------------------------------
        # 实例化核心模块
        # ------------------------------------------------------------------
        self.event_bus: EventBus = EventBus()
        self.decision_engine: ContextDecisionEngine = ContextDecisionEngine()
        self.budget_manager: ContextBudgetManager = ContextBudgetManager()
        self.memory_bank: MemoryBank = MemoryBank()
        self.memory_router: MemoryRouter = MemoryRouter(self.memory_bank)
        self.evaluator: Evaluator = evaluator if evaluator is not None else Evaluator(llm_client=llm_client)
        self.bad_case_manager: BadCaseManager = BadCaseManager()
        self.rag_manager: RagContextManager = RagContextManager()
        self.knowledge_graph: TemporalKnowledgeGraph = TemporalKnowledgeGraph()
        self.version_control: VersionControlManager = VersionControlManager()
        self.tool_hub: ToolHub = ToolHub()
        self.sandbox: Sandbox = Sandbox()
        self.trace_storage: TraceStorage = TraceStorage()

        # ------------------------------------------------------------------
        # V3 新增模块实例化
        # ------------------------------------------------------------------
        self.storage: StableAgentStorage = StableAgentStorage()
        self.token_meter: TokenMeter = TokenMeter()
        self.context_triage: ContextTriage = ContextTriage(self.token_meter)
        self.context_pack_builder: ContextPackBuilder = ContextPackBuilder(
            self.context_triage
        )
        self.retrieval_policy: RetrievalPolicy = RetrievalPolicy()
        self.retrieval_critic: RetrievalCritic = RetrievalCritic(self.token_meter)
        self.plain_language: PlainLanguageExplainer = PlainLanguageExplainer()
        self.security_policy: SecurityPolicy = SecurityPolicy()
        self.approval_manager: ApprovalManager = ApprovalManager(self.storage)
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            from stable_agent.llm_factory import get_llm_client
            self.llm_client = get_llm_client()
        self.eval_dataset_mgr: EvalDatasetManager = EvalDatasetManager()

        # V6.2: MCPToolRegistry (V3) 已物理删除。工具注册走 gateway/unified_tool_registry.py

        # V6.0: Self-Improvement Proof Loop
        self.proof_loop: SelfImprovementProofLoop = SelfImprovementProofLoop(
            memory_store=MemoryUpdateStore(),
            patch_store=SkillPatchStore(),
            min_confidence=0.6,
            storage=self.storage,  # V6.2: 回归用例持久化
        )
        # V6.2: 验证时优先使用 LLM eval（如果 llm_client 可用）
        try:
            self.proof_loop._validator.llm_client = self.llm_client if hasattr(self.llm_client, 'generate') else None
        except Exception:
            pass  # llm_client 不可用时 fallback 规则评分

        # V6.1: Temporal Memory Bridge + Context Compression Guard
        self.temporal_memory_bridge: TemporalMemoryBridge = TemporalMemoryBridge()
        self.context_compression_guard: ContextCompressionGuard = ContextCompressionGuard()

        # 初始化持久化数据库
        self.storage.init_db()

        # ------------------------------------------------------------------
        # 建立模块连接
        # ------------------------------------------------------------------
        # 将 EventBus 注入 WorkflowEngine（含 V3 模块）
        self.workflow_engine: WorkflowEngine = WorkflowEngine(
            decision_engine=self.decision_engine,
            budget_manager=self.budget_manager,
            memory_router=self.memory_router,
            evaluator=self.evaluator,
            bad_case_manager=self.bad_case_manager,
            event_bus=self.event_bus,
            llm_client=self.llm_client,
            security_policy=self.security_policy,
            approval_manager=self.approval_manager,
            token_meter=self.token_meter,
        )

        # 将 EventBus 订阅到 TraceStorage（自动持久化事件）
        self.event_bus.subscribe(self.trace_storage.save_event)

        # ------------------------------------------------------------------
        # 预填充示例记忆
        # ------------------------------------------------------------------
        sample_memories: list[MemoryItem] = [
            MemoryItem(
                id="mem-001",
                content="登录页面 CSS 使用了 flexbox 布局",
                type="project_constraint",
                timestamp=time.time(),
                priority=0.8,
                source="project_init",
                status="active",
            ),
            MemoryItem(
                id="mem-002",
                content="上次修改登录页面时遗漏了移动端适配",
                type="bad_case",
                timestamp=time.time(),
                priority=0.9,
                source="bug_history",
                status="active",
            ),
            MemoryItem(
                id="mem-003",
                content="UI 组件库使用 MUI v5，主题色为蓝色系 #1976D2",
                type="project_constraint",
                timestamp=time.time(),
                priority=0.7,
                source="project_init",
                status="active",
            ),
            MemoryItem(
                id="mem-004",
                content="重构时先写测试再改代码，上次跳过测试导致回归 bug",
                type="bad_case",
                timestamp=time.time(),
                priority=0.85,
                source="lesson_learned",
                status="active",
            ),
            MemoryItem(
                id="mem-005",
                content="JWT token 有效期设为 24 小时，存储在 localStorage",
                type="project_constraint",
                timestamp=time.time(),
                priority=0.6,
                source="security_policy",
                status="active",
            ),
        ]
        for item in sample_memories:
            self.memory_bank.add_item(item)

        # ------------------------------------------------------------------
        # 注册示例工具
        # ------------------------------------------------------------------
        def _format_code(code: str, language: str = "python") -> str:
            """示例工具：格式化代码。"""
            return f"```{language}\n{code}\n```"

        def _count_lines(text: str) -> int:
            """示例工具：统计行数。"""
            return len(text.splitlines())

        self.tool_hub.register_tool(
            name="format_code",
            tool_callable=_format_code,
            schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "language": {"type": "string", "default": "python"},
                },
                "required": ["code"],
            },
            description="将代码格式化为 Markdown 代码块",
        )
        self.tool_hub.register_tool(
            name="count_lines",
            tool_callable=_count_lines,
            schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                },
                "required": ["text"],
            },
            description="统计文本行数",
        )

        # 发布系统初始化事件
        self.event_bus.publish(
            Event(
                timestamp=time.time(),
                type="system:initialized",
                payload={
                    "module_count": 24,  # V3: 从 12 升级到 24
                    "memory_count": len(sample_memories),
                    "version": "v3",
                },
            )
        )

        # ------------------------------------------------------------------
        # 当前运行上下文（V3 新增）
        # ------------------------------------------------------------------
        self._current_run_id: Optional[str] = None
        self._current_workflow: Optional[Workflow] = None

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def process_task(self, task_input: str) -> dict:
        """处理用户任务，完成端到端的 V3 执行流程。

        V6.0 升级：新增第 14.5 步 Self-Improvement Proof Loop。
        V3 升级为 17+ 步流程：
        1. 多标签分类 → 2. 风险检测 → 3. 动态预算分配
        → 4. 检索策略判断 → 5. 分层记忆检索 → 6. RAG 检索 + 批判
        → 7. 上下文包构建 → 8. 审批判断 → 9. 发布构建事件
        → 10. 启动工作流 → 11. 合并上下文 → 12. 循环推进
        → 13. 提取评估 → 14. bad case 记录 → 14.5 Self-Improvement
        → 15. 持久化 run → 16. 存储 context_pack → 17. 返回结果

        Args:
            task_input: 用户的自然语言任务描述。

        Returns:
            包含 task_type, workflow_state, evaluation, events_count,
            context_pack, risk, run_id, si_report 的字典。

        Examples:
            >>> orchestrator = StableAgentOrchestrator()
            >>> result = orchestrator.process_task("修复登录页面的样式错位问题")
            >>> "task_type" in result
            True
            >>> "risk" in result
            True
            >>> "context_pack" in result
            True
        """
        # 1. 多标签分类
        scores: dict = self.decision_engine.classify_task_multi(task_input)
        task_type: TaskType = self.decision_engine.get_primary_task(scores)

        # 2. 风险检测
        risk: str = self.decision_engine.detect_risk_level(task_input)

        # 3. 动态预算分配
        budget: dict[str, int] = self.budget_manager.compute_budget(task_type)

        # 4. 检索策略判断
        should_rag: bool = self.retrieval_policy.should_retrieve(
            task_type, task_input
        )

        # 5. 分层记忆检索
        memories: list[MemoryItem] = self.memory_router.query_for_task(
            task_input=task_input,
            task_type=task_type,
        )
        # 更新记忆使用记录
        for mem in memories:
            mem.last_used_at = time.time()
            mem.usage_count += 1
            try:
                self.storage.save_memory(mem)
            except Exception as e:
                logger.warning("存储操作失败，继续执行: %s", e)

        # 裁剪记忆
        pruned_memories: list[MemoryItem] = self.budget_manager.prune_memory(
            memories, budget["memory"]
        )

        # 6. RAG 检索 + 批判
        rag_chunks: list[dict] = []
        if should_rag:
            try:
                raw_chunks = self.rag_manager.retrieve_rich(task_input)
                # retrieve_rich 可能返回 list 或 dict
                if isinstance(raw_chunks, list):
                    rag_chunks = self.retrieval_critic.critique(
                        task_input, raw_chunks
                    )
                else:
                    rag_chunks = []
            except Exception as e:
                # 回退到 build_context_pack
                logger.warning("RAG 检索失败，回退到 build_context_pack: %s", e)
                try:
                    rag_chunks = self.rag_manager.build_context_pack(
                        task_type, budget["rag"]
                    )
                except Exception as e2:
                    logger.warning("RAG build_context_pack 回退也失败: %s", e2)
                    rag_chunks = []

        # 6.5 (V6.1) Temporal Memory Retrieval + Context Compression Guard
        _run_id = self._current_run_id or str(uuid.uuid4())
        try:
            # 加载项目记忆到 TemporalMemoryRouter
            project_id = getattr(self, "_project_id", None)
            temporal_hits = self.temporal_memory_bridge.load_for_project(
                project_id=project_id,
                existing_memories=[{
                    "id": m.memory_id,
                    "content": m.content,
                    "created_at": m.created_at,
                    "source": "memory_bank",
                } for m in pruned_memories if hasattr(m, 'content')],
            )

            # 检索相关时间记忆
            temporal_results = self.temporal_memory_bridge.retrieve(
                task_input=task_input,
                project_id=project_id,
                top_k=8,
            )

            # 发布 temporal_memory.retrieved 事件
            self.event_bus.publish(Event(
                timestamp=time.time(),
                type="temporal_memory.retrieved",
                payload={
                    "run_id": _run_id,
                    "hit_count": len(temporal_results),
                    "hits": [{"memory_id": h.memory_id, "reason_zh": h.reason_zh}
                             for h in temporal_results[:5]],
                },
            ))
            logger.info("TemporalMemory: 检索到 %d 条时间记忆", len(temporal_results))

            # Context Compression Guard
            context_items_for_guard = [
                {"content": m.content, "type": "memory", "confidence": getattr(m, 'confidence', 0.5)}
                for m in pruned_memories if hasattr(m, 'content')
            ]
            # 添加 RAG chunks
            for rc in rag_chunks:
                if isinstance(rc, dict) and rc.get("content"):
                    context_items_for_guard.append({**rc, "type": "rag"})

            compression_decision = self.context_compression_guard.protect(
                task_input=task_input,
                context_items=context_items_for_guard,
                temporal_memories=temporal_results,
                token_budget=budget.get("context", 8000),
            )

            # apply enforce_budget
            compression_decision = self.context_compression_guard.enforce_budget(
                decision=compression_decision,
                token_budget=budget.get("context", 8000),
            )

            # 发布 context.compression_guard.checked 事件
            self.event_bus.publish(Event(
                timestamp=time.time(),
                type="context.compression_guard.checked",
                payload={
                    "run_id": _run_id,
                    "protected_count": len(compression_decision.protected_items),
                    "dropped_count": len(compression_decision.dropped_items),
                    "kept_count": len(compression_decision.kept_items),
                    "risk_flags": compression_decision.risk_flags,
                    "blocked": compression_decision.blocked,
                    "summary_zh": compression_decision.summary_zh,
                },
            ))
            logger.info("ContextCompressionGuard: %s", compression_decision.summary_zh)
        except Exception as e:
            logger.warning("TemporalMemory/CompressionGuard 执行失败，跳过: %s", e)

        # 7. 上下文包构建
        context_pack: ContextPack = self.context_triage.build_context_pack(
            task_input=task_input,
            task_type=task_type,
            memories=pruned_memories,
            rag_chunks=rag_chunks,
            budget=8000,
        )

        # 8. 审批判断
        approval_required: bool = self.decision_engine.should_require_approval(
            task_input, task_type
        )
        if approval_required:
            run_id = self._current_run_id or str(uuid.uuid4())
            self.approval_manager.create_request(
                run_id=run_id,
                action=task_input[:100],
                risk=risk,
                reason=f"任务类型 {task_type.value} 需要审批",
            )
        else:
            # V6.1 fix: 确保 run_id 在所有分支都被定义
            run_id = self._current_run_id or str(uuid.uuid4())

        # 发布 budget:allocated 事件
        self.event_bus.publish(
            Event(
                timestamp=time.time(),
                type="budget:allocated",
                payload={
                    "task_type": task_type.value,
                    "budget": budget,
                    "risk": risk,
                },
            )
        )

        # 9. 发布 "context:built" 事件
        self.event_bus.publish(
            Event(
                timestamp=time.time(),
                type="context:built",
                payload={
                    "task_type": task_type.value,
                    "memory_count": len(pruned_memories),
                    "rag_doc_count": len(rag_chunks),
                    "budget": budget,
                    "pack_id": context_pack.pack_id,
                    "total_tokens": context_pack.total_tokens,
                },
            )
        )

        # 10. 启动工作流（创建 Workflow，状态为 INIT）
        workflow: Workflow = self.workflow_engine.start_workflow(task_input)
        self._current_workflow = workflow

        # 11. 合并预构建的上下文到 workflow.context_pack
        workflow.context_pack["orchestrator_memory"] = [
            {"id": m.id, "content": m.content, "type": m.type, "priority": m.priority}
            for m in pruned_memories
        ]
        workflow.context_pack["orchestrator_rag"] = rag_chunks
        workflow.context_pack["context_pack"] = {
            "pack_id": context_pack.pack_id,
            "total_tokens": context_pack.total_tokens,
            "item_count": len(context_pack.items),
        }
        workflow.context_pack["risk"] = risk

        # 12. 循环推进工作流直到 COMPLETE
        from stable_agent.models import WorkflowState

        max_steps: int = 20  # 安全上限，防止死循环
        for _ in range(max_steps):
            if workflow.current_state == WorkflowState.COMPLETE:
                break
            self.workflow_engine.next_step(workflow)

        # 13. 提取评估结果
        eval_data: dict = workflow.context_pack.get("evaluation", {})
        evaluation: Optional[EvaluationResult] = None
        if eval_data:
            try:
                evaluation = EvaluationResult(
                    completion_rate=eval_data.get("completion_rate", 0.0),
                    context_hit_rate=eval_data.get("context_hit_rate", 0.0),
                    token_efficiency=eval_data.get("token_efficiency", 0.0),
                    hallucination_score=eval_data.get("hallucination_score", 0.0),
                    user_preference_score=eval_data.get("user_preference_score", 0.0),
                    overall_score=eval_data.get("overall_score", 0.0),
                )
            except ValueError:
                evaluation = None

        # 14. 如果 overall_score < 0.5，记录 bad_case
        if evaluation is not None and evaluation.overall_score < 0.5:
            bad_case = self.bad_case_manager.record_case(
                task=task_type,
                input_context=task_input,
                output=workflow.context_pack.get("output", ""),
                evaluation=evaluation,
            )
            # 持久化 bad case
            if bad_case is not None:
                try:
                    self.storage.save_bad_case(bad_case)
                except Exception as e:
                    logger.warning("存储操作失败，继续执行: %s", e)

        # 14.5 (V6.0) Self-Improvement Proof Loop
        si_report = None
        try:
            eval_passed = evaluation is not None and evaluation.overall_score >= 0.6
            failure_mode = ""
            if evaluation is not None and evaluation.overall_score < 0.6:
                # 推断失败模式
                if evaluation.hallucination_score < 0.5:
                    failure_mode = "hallucination"
                elif evaluation.completion_rate < 0.5:
                    failure_mode = "incomplete_output"
                elif evaluation.token_efficiency < 0.3:
                    failure_mode = "token_waste"
                else:
                    failure_mode = "low_quality"

            si_report = self.proof_loop.evaluate_and_learn(
                run_id=run_id if run_id else str(uuid.uuid4()),
                eval_passed=eval_passed,
                eval_score=evaluation.overall_score if evaluation else 0.0,
                eval_reason=(
                    f"overall_score={evaluation.overall_score:.2f}" if evaluation else "无评估"
                ),
                failure_mode=failure_mode,
                observations=[{"text": workflow.context_pack.get("output", "")}],
            )
            logger.info(
                "Self-improv: learning_triggered=%s, regressions=%d, memories=%d, patches=%d",
                si_report.learning_triggered,
                len(si_report.regression_cases),
                len(si_report.memory_candidates),
                len(si_report.skill_patches),
            )
        except Exception as e:
            logger.warning("Self-Improvement ProofLoop 执行失败，继续: %s", e)

        # 15. 持久化 run 记录
        run_id = self._current_run_id or str(uuid.uuid4())
        run_record = RunRecord(
            run_id=run_id,
            user_task=task_input,
            task_type=task_type,
            status="completed" if evaluation is not None else "completed",
            started_at=time.time(),
            ended_at=time.time(),
            overall_score=evaluation.overall_score if evaluation else None,
        )
        try:
            self.storage.save_run(run_record)
        except Exception as e:
            logger.warning("存储操作失败，继续执行: %s", e)

        # 16. 持久化 context_pack
        context_pack.run_id = run_id
        try:
            self.storage.save_context_pack(context_pack)
        except Exception as e:
            logger.warning("存储操作失败，继续执行: %s", e)

        # 17. 返回结构化结果
        events_count: int = len(self.event_bus._events)

        return {
            "task_type": task_type,
            "workflow_state": workflow.current_state,
            "evaluation": evaluation,
            "events_count": events_count,
            "context_pack": context_pack,
            "risk": risk,
            "run_id": run_id,
            "si_report": si_report.to_dict() if si_report else None,
        }

    # ------------------------------------------------------------------
    # V3 新增方法
    # ------------------------------------------------------------------

    def start_run(self, task_input: str) -> RunRecord:
        """创建 RunRecord 并持久化到 storage。

        Args:
            task_input: 用户任务输入文本。

        Returns:
            创建的 RunRecord 实例。
        """
        run_id = str(uuid.uuid4())
        record = RunRecord(
            run_id=run_id,
            user_task=task_input,
            task_type=TaskType.GENERAL_QA,
            status="init",
            started_at=time.time(),
        )
        self._current_run_id = run_id

        # 持久化
        try:
            self.storage.save_run(record)
        except Exception as e:
            logger.warning("存储操作失败，继续执行: %s", e)

        # 发布 run:started 事件
        self.event_bus.publish(
            Event(
                timestamp=time.time(),
                type="run:started",
                payload={"run_id": run_id, "task": task_input},
            )
        )

        return record

    def resume_run(self, run_id: str) -> dict:
        """从 storage 恢复并继续运行。

        Args:
            run_id: 运行 ID。

        Returns:
            恢复状态字典。
        """
        record: Optional[RunRecord] = self.storage.get_run(run_id)
        if record is None:
            return {
                "ok": False,
                "run_id": run_id,
                "message": f"Run '{run_id}' not found",
            }

        self._current_run_id = run_id

        # 更新状态
        try:
            self.storage.update_run(run_id, {"status": "running"})
        except Exception as e:
            logger.warning("存储操作失败，继续执行: %s", e)

        # 发布 run:resumed 事件
        self.event_bus.publish(
            Event(
                timestamp=time.time(),
                type="run:resumed",
                payload={"run_id": run_id},
            )
        )

        return {
            "ok": True,
            "run_id": run_id,
            "record": record,
            "message": "Run resumed",
        }

    def get_run_status(self, run_id: str) -> dict:
        """查询 run 当前状态。

        Args:
            run_id: 运行 ID。

        Returns:
            状态字典。
        """
        record: Optional[RunRecord] = self.storage.get_run(run_id)
        if record is None:
            return {
                "ok": False,
                "run_id": run_id,
                "status": "not_found",
            }

        spans: list[TraceSpan] = self.storage.load_spans(run_id)

        return {
            "ok": True,
            "run_id": record.run_id,
            "task": record.user_task,
            "task_type": record.task_type.value,
            "status": record.status,
            "started_at": record.started_at,
            "ended_at": record.ended_at,
            "total_input_tokens": record.total_input_tokens,
            "total_output_tokens": record.total_output_tokens,
            "total_cost_estimate": record.total_cost_estimate,
            "overall_score": record.overall_score,
            "span_count": len(spans),
        }

    def get_run_trace(self, run_id: str) -> list[TraceSpan]:
        """获取 run 的完整 trace。

        Args:
            run_id: 运行 ID。

        Returns:
            TraceSpan 列表，按 started_at 升序排列。
        """
        return self.storage.load_spans(run_id)

    def build_context_pack_api(self, task_input: str) -> ContextPack:
        """对外 API：构建上下文包。

        不需要完整 process_task 流程，仅构建上下文包。

        Args:
            task_input: 用户任务输入文本。

        Returns:
            构建完成的 ContextPack 实例。
        """
        # 任务分类
        task_type: TaskType = self.decision_engine.classify_task(task_input)

        # 检索记忆
        memories: list[MemoryItem] = self.memory_router.query_for_task(
            task_input=task_input, task_type=task_type
        )

        # RAG 检索
        should_rag: bool = self.retrieval_policy.should_retrieve(
            task_type, task_input
        )
        rag_chunks: list[dict] = []
        if should_rag:
            try:
                raw_chunks = self.rag_manager.retrieve_rich(task_input)
                if isinstance(raw_chunks, list):
                    rag_chunks = self.retrieval_critic.critique(
                        task_input, raw_chunks
                    )
            except Exception as e:
                logger.warning("RAG 检索失败，回退为空: %s", e)
                rag_chunks = []

        # 构建上下文包
        budget: dict[str, int] = self.budget_manager.compute_budget(task_type)
        pack: ContextPack = self.context_triage.build_context_pack(
            task_input=task_input,
            task_type=task_type,
            memories=memories,
            rag_chunks=rag_chunks,
            budget=budget.get("prompt_budget", 8000),
        )

        return pack

    def get_summary(self) -> dict:
        """获取系统当前状态摘要。

        V3 升级：包含 run_count 和更详细的模块信息。

        Returns:
            包含 memory_count, event_count, bad_case_count, tool_count,
            run_count 的字典。

        Examples:
            >>> orchestrator = StableAgentOrchestrator()
            >>> summary = orchestrator.get_summary()
            >>> "memory_count" in summary
            True
            >>> "run_count" in summary
            True
            >>> summary["memory_count"] >= 5  # 预填充了 5 条
            True
        """
        runs: list[RunRecord] = []
        try:
            runs = self.storage.list_runs(limit=1000)
        except Exception as e:
            logger.warning("存储操作失败，继续执行: %s", e)

        return {
            "memory_count": len(self.memory_bank._items),
            "event_count": len(self.event_bus._events),
            "bad_case_count": len(
                self.bad_case_manager.retrieve_recent_bad_cases(limit=1000)
            ),
            "tool_count": len(self.tool_hub.tools),
            "run_count": len(runs),
        }


# ============================================================================
# run_demo — 完整演示入口
# ============================================================================


def run_demo() -> None:
    """运行 StableAgent OS 完整演示。

    创建 StableAgentOrchestrator 实例，执行两个示例任务，
    并输出系统摘要。演示了从任务分类到工作流完成的完整流程。
    """
    print("=" * 60)
    print("  StableAgent OS V3 — 演示开始")
    print("=" * 60)

    orchestrator: StableAgentOrchestrator = StableAgentOrchestrator()

    # 演示任务列表
    tasks: list[str] = [
        "修复登录页面的样式错位问题",
        "重构用户认证模块，改用 JWT 方案",
    ]

    for task_input in tasks:
        print(f"\n{'=' * 60}")
        print(f"  任务：{task_input}")
        print(f"{'=' * 60}")

        result: dict = orchestrator.process_task(task_input)

        task_type: TaskType = result["task_type"]
        evaluation: Optional[EvaluationResult] = result.get("evaluation")
        events_count: int = result.get("events_count", 0)
        risk: str = result.get("risk", "unknown")
        run_id: str = result.get("run_id", "N/A")

        print(f"  → 任务分类：{task_type.value}")
        print(f"  → 风险等级：{risk}")
        print(f"  → Run ID：{run_id}")
        if evaluation is not None:
            print(f"  → 完成度：{evaluation.completion_rate:.2f}")
            print(f"  → 整体评分：{evaluation.overall_score:.2f}")
        else:
            print(f"  → 完成度：N/A")
            print(f"  → 整体评分：N/A")
        print(f"  → 产生事件：{events_count} 条")

    # 系统摘要
    summary: dict = orchestrator.get_summary()
    print(f"\n{'=' * 60}")
    print(f"  系统摘要 (V3)")
    print(f"{'=' * 60}")
    print(f"  → 记忆条目：{summary['memory_count']} 条")
    print(f"  → 事件总数：{summary['event_count']} 条")
    print(f"  → Bad Case：{summary['bad_case_count']} 条")
    print(f"  → 注册工具：{summary['tool_count']} 个")
    print(f"  → 历史 Run：{summary['run_count']} 个")
    print(f"\n{'=' * 60}")
    print(f"  演示结束")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run_demo()
