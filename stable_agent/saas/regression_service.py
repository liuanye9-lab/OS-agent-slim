"""回归用例服务。

将 BadCase 转换为 RegressionCase，管理回归用例集。

核心流程：
1. 从 BadCase 创建 RegressionCase
2. 追加到项目的回归数据集
3. 用于 Validation Gate 的回归检测

用法::

    svc = RegressionService(repo)
    reg_case = svc.create_from_bad_case(
        bad_case_id="bc_xxx",
        project_id="proj_xxx",
        workspace_id="ws_xxx",
    )
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from stable_agent.models import BadCase
from stable_agent.saas.models import RegressionCaseRecord, _new_id, _now
from stable_agent.saas.repository import SaasRepository

logger = logging.getLogger(__name__)

# 回归用例持久化文件（与 V6-Professional 保持一致）
REGRESSION_CASES_FILE = "data/regression_cases.jsonl"


class RegressionService:
    """回归用例服务。

    管理 BadCase → RegressionCase 的转换和持久化。

    Attributes:
        repo: SaaS 数据访问层实例。
    """

    def __init__(self, repo: SaasRepository | None = None) -> None:
        self.repo: SaasRepository = repo or SaasRepository()

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    def create_from_bad_case(
        self,
        bad_case: BadCase,
        workspace_id: str = "",
        project_id: str = "",
    ) -> RegressionCaseRecord:
        """从 BadCase 创建 RegressionCase。

        使用 BadCase 的输入上下文、失败原因、评分生成回归用例。
        同步追加到 JSONL 文件和 SQLite 数据库。

        Args:
            bad_case: BadCase 实例。
            workspace_id: 工作空间 ID。
            project_id: 项目 ID。

        Returns:
            创建的 RegressionCaseRecord。
        """
        # 提取失败归因
        failure_attribution = bad_case.evaluation.failure_attribution
        failure_mode = failure_attribution.get("failed_stage", "unknown")
        reason = failure_attribution.get("reason", bad_case.failure_reason)

        # 构建期望行为
        expected_behavior = (
            f"应当避免 {failure_mode} 阶段的失败：{reason}。"
            f"原始任务：{bad_case.input_context[:100]}..."
        )

        # 创建回归用例
        case = RegressionCaseRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            task_input=bad_case.input_context,
            expected_behavior=expected_behavior,
            failure_mode=failure_mode,
            source_run_id=bad_case.source_run_id,
            source_bad_case_id=bad_case.id,
            tags=bad_case.tags or ["eval", "skillopt"],
            overall_score=bad_case.evaluation.overall_score,
        )

        # 持久化到 SQLite
        ok = self.repo.save_regression_case(case)
        if not ok:
            logger.warning("Failed to save regression case to DB: %s", case.id)

        # 追加到 JSONL 文件
        self._append_to_jsonl(case)

        logger.info(
            "Created regression case %s from bad_case %s (failure_mode=%s)",
            case.id, bad_case.id, failure_mode,
        )
        return case

    def create_from_bad_case_dict(self, bad_case_dict: dict[str, Any]) -> RegressionCaseRecord | None:
        """从 BadCase 字典创建 RegressionCase。

        用于通过 MCP/API 接收的 BadCase 数据。

        Args:
            bad_case_dict: BadCase 的 JSON 序列化字典。
                需要字段：id, input_context, failure_reason, source_run_id,
                tags, overall_score, failure_attribution

        Returns:
            创建的 RegressionCaseRecord，失败返回 None。
        """
        try:
            failure_attribution = bad_case_dict.get("failure_attribution", {})
            if isinstance(failure_attribution, str):
                failure_attribution = json.loads(failure_attribution)

            failure_mode = failure_attribution.get("failed_stage", "unknown")
            reason = failure_attribution.get("reason", bad_case_dict.get("failure_reason", ""))

            case = RegressionCaseRecord(
                workspace_id=bad_case_dict.get("workspace_id", ""),
                project_id=bad_case_dict.get("project_id", ""),
                task_input=bad_case_dict.get("input_context", ""),
                expected_behavior=f"应当避免 {failure_mode} 阶段的失败：{reason}",
                failure_mode=failure_mode,
                source_run_id=bad_case_dict.get("source_run_id", ""),
                source_bad_case_id=bad_case_dict.get("id", ""),
                tags=bad_case_dict.get("tags", ["eval"]),
                overall_score=bad_case_dict.get("overall_score", 0.0),
            )

            self.repo.save_regression_case(case)
            self._append_to_jsonl(case)
            return case
        except Exception as e:
            logger.warning("Failed to create regression case from dict: %s", e)
            return None

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_cases(self, project_id: str) -> list[RegressionCaseRecord]:
        """列出项目的所有回归用例。"""
        return self.repo.list_regression_cases(project_id)

    def to_validation_cases(self, project_id: str) -> list[dict[str, Any]]:
        """将回归用例转换为 Validation Gate 兼容格式。

        Args:
            project_id: 项目 ID。

        Returns:
            验证用例字典列表。
        """
        cases = self.repo.list_regression_cases(project_id)
        return [
            {
                "id": c.id,
                "task_input": c.task_input,
                "expected_behavior": c.expected_behavior,
                "failure_mode": c.failure_mode,
            }
            for c in cases
        ]

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def _append_to_jsonl(self, case: RegressionCaseRecord) -> None:
        """追加回归用例到 JSONL 文件（与 V6-Professional 兼容）。"""
        try:
            file_path = Path(REGRESSION_CASES_FILE)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            record = {
                "id": case.id,
                "task_input": case.task_input,
                "expected_behavior": case.expected_behavior,
                "failure_mode": case.failure_mode,
                "source_run_id": case.source_run_id,
                "source_bad_case_id": case.source_bad_case_id,
                "created_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(case.created_at)
                ),
                "tags": case.tags,
                "overall_score": case.overall_score,
            }

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to append regression case to JSONL: %s", e)

    @staticmethod
    def load_regression_cases_from_file() -> list[dict[str, Any]]:
        """从 JSONL 文件加载回归用例（供 ValidationGate 使用）。"""
        file_path = Path(REGRESSION_CASES_FILE)
        if not file_path.exists():
            return []

        cases: list[dict[str, Any]] = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        cases.append(json.loads(line))
        except Exception as e:
            logger.warning("Failed to load regression cases from JSONL: %s", e)

        return cases
