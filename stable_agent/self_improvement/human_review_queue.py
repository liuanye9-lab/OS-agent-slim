"""HumanReviewQueue — 人工审核队列 + MCP 通道。

V6.3: 替换 ProofLoop 中 submit_for_review 仅状态变更的问题。
提供：
1. ReviewRequest 数据结构 — 含 patch 完整上下文供人审核
2. ReviewQueue — 内存队列，供 MCP/API 查询 pending reviews
3. review_notification — 生成可读的审核通知摘要

External API 端点（由 Dashboard/API 层暴露）：
- GET /api/reviews/pending → list pending review requests
- POST /api/reviews/{id}/approve → approve
- POST /api/reviews/{id}/reject → reject

注意：不依赖飞书/MCP 外部服务，仅提供标准接口，
上层可以包装成飞书消息/邮件/REST API。
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ReviewRequest:
    """人工审核请求。"""

    review_id: str = field(default_factory=lambda: f"review_{uuid.uuid4().hex[:8]}")
    patch_id: str = ""
    run_id: str = ""
    failure_mode: str = ""
    old_rule: str = ""
    new_rule: str = ""
    expected_improvement: str = ""
    risk_level: str = "low"
    validation_report_id: str = ""
    status: str = "pending"  # pending / approved / rejected
    created_at: float = field(default_factory=time.time)
    resolved_at: float | None = None
    resolution: str = ""

    def to_notification(self) -> str:
        """生成人类可读的审核通知摘要。"""
        lines = [
            f"## 人工审核请求",
            f"",
            f"**Patch ID**: `{self.patch_id}`",
            f"**Run**: `{self.run_id}`",
            f"**失败模式**: {self.failure_mode}",
            f"**风险等级**: {self.risk_level}",
            f"",
            f"### 旧规则",
            f"```",
            self.old_rule or "(无旧规则)",
            f"```",
            f"",
            f"### 新规则",
            f"```",
            self.new_rule,
            f"```",
            f"",
            f"**预期改进**: {self.expected_improvement}",
            f"",
            f"---",
            f"审批: `POST /api/reviews/{self.review_id}/{{approve|reject}}`",
        ]
        return "\n".join(lines)


class HumanReviewQueue:
    """人工审核队列。

    Usage:
        queue = HumanReviewQueue()
        req = queue.submit(patch_id=..., old_rule=..., new_rule=...)
        # Dashboard/API 查询
        pending = queue.list_pending()
        # 审核
        queue.approve(req.review_id)
    """

    def __init__(self) -> None:
        self._requests: dict[str, ReviewRequest] = {}
        self._history: list[ReviewRequest] = []

    def submit(
        self,
        patch_id: str,
        run_id: str = "",
        failure_mode: str = "",
        old_rule: str = "",
        new_rule: str = "",
        expected_improvement: str = "",
        risk_level: str = "low",
        validation_report_id: str = "",
    ) -> ReviewRequest:
        """提交审核请求。

        Args:
            patch_id: Skill Patch ID。
            run_id: 关联的 run ID。
            failure_mode: 失败模式。
            old_rule: 旧规则文本。
            new_rule: 新规则文本。
            expected_improvement: 预期改进。
            risk_level: 风险等级。
            validation_report_id: 验证报告 ID。

        Returns:
            ReviewRequest 实例。
        """
        req = ReviewRequest(
            patch_id=patch_id,
            run_id=run_id,
            failure_mode=failure_mode,
            old_rule=old_rule,
            new_rule=new_rule,
            expected_improvement=expected_improvement,
            risk_level=risk_level,
            validation_report_id=validation_report_id,
        )
        self._requests[req.review_id] = req
        logger.info("ReviewRequest submitted: %s (patch=%s, risk=%s)",
                     req.review_id, patch_id, risk_level)
        return req

    def list_pending(self) -> list[ReviewRequest]:
        """列出所有待审核的请求。"""
        return [r for r in self._requests.values() if r.status == "pending"]

    def list_all(self) -> list[ReviewRequest]:
        """列出所有请求（含已处理的）。"""
        return list(self._requests.values()) + self._history

    def approve(self, review_id: str) -> ReviewRequest | None:
        """审核通过。

        Args:
            review_id: 审核请求 ID。

        Returns:
            更新后的 ReviewRequest 或 None。
        """
        req = self._requests.get(review_id)
        if req is None:
            logger.warning("ReviewRequest %s 不存在", review_id)
            return None

        req.status = "approved"
        req.resolved_at = time.time()
        req.resolution = "approved"
        self._history.append(req)
        del self._requests[review_id]
        logger.info("ReviewRequest approved: %s", review_id)
        return req

    def reject(self, review_id: str, reason: str = "") -> ReviewRequest | None:
        """审核拒绝。

        Args:
            review_id: 审核请求 ID。
            reason: 拒绝原因。

        Returns:
            更新后的 ReviewRequest 或 None。
        """
        req = self._requests.get(review_id)
        if req is None:
            logger.warning("ReviewRequest %s 不存在", review_id)
            return None

        req.status = "rejected"
        req.resolved_at = time.time()
        req.resolution = f"rejected: {reason}" if reason else "rejected"
        self._history.append(req)
        del self._requests[review_id]
        logger.info("ReviewRequest rejected: %s (reason=%s)", review_id, reason)
        return req

    def get(self, review_id: str) -> ReviewRequest | None:
        """获取指定 review 请求。"""
        return self._requests.get(review_id)

    @property
    def pending_count(self) -> int:
        """待审核数量。"""
        return len(self.list_pending())
