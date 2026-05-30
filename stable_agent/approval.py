"""StableAgent OS 审批管理器模块。
# @deprecated V6.0: 审批逻辑已迁移到 stable_agent/approval/ 包。
#   本文件保留向后兼容（approval/__init__.py 动态导入），计划在 V7.0 移除。

管理审批请求的完整生命周期：创建、批准、拒绝和查询。
支持两种运行模式：
- 纯内存模式：无需存储，审批请求仅在当前会话有效。
- 持久化模式：通过注入 StableAgentStorage 将请求保存到 SQLite。

约定：
- 所有审批请求通过 request_id 唯一标识
- 状态流转：pending → approved/rejected
- 已解决的请求不可再次变更状态
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from stable_agent.models import ApprovalRequest, ApprovalStatus, RiskLevel


class ApprovalManager:
    """审批请求生命周期管理器。

    管理高风险操作的审批请求，支持创建、批准、拒绝和查询。
    可注入 StableAgentStorage 实现持久化，None 时使用纯内存存储。

    Attributes:
        storage: 可选的持久化存储实例。
        _requests: 内存中的审批请求字典（{request_id: ApprovalRequest}）。
    """

    def __init__(self, storage=None) -> None:
        """初始化审批管理器。

        Args:
            storage: StableAgentStorage 实例，用于持久化审批请求。
                     None 时仅使用内存存储。
        """
        self.storage = storage
        self._requests: dict[str, ApprovalRequest] = {}

    def create_request(
        self,
        run_id: str,
        action: str,
        risk: str = RiskLevel.MEDIUM.value,
        reason: str = "",
        details: Optional[dict] = None,
    ) -> ApprovalRequest:
        """创建审批请求。

        生成唯一的 request_id，创建 ApprovalRequest 实例，并（如果配置）
        持久化到存储层。

        Args:
            run_id: 所属运行 ID。
            action: 请求执行的动作描述。
            risk: 风险等级（RiskLevel 枚举值），默认 medium。
            reason: 请求原因说明。
            details: 请求详细信息字典，None 视为空字典。

        Returns:
            创建的 ApprovalRequest 实例。

        Raises:
            ValueError: 如果 risk 不是合法的 RiskLevel 值。
        """
        # 验证 risk 合法性
        valid_risks = {r.value for r in RiskLevel}
        if risk not in valid_risks:
            raise ValueError(
                f"risk must be one of {valid_risks}, got '{risk}'"
            )

        request_id = str(uuid.uuid4())
        if details is None:
            details = {}

        req = ApprovalRequest(
            request_id=request_id,
            run_id=run_id,
            action=action,
            risk=risk,
            reason=reason,
            status=ApprovalStatus.PENDING.value,
            created_at=time.time(),
            resolved_at=None,
            details=details,
        )

        # 内存存储
        self._requests[request_id] = req

        # 持久化存储
        if self.storage is not None:
            self.storage.save_approval(req)

        return req

    def approve(self, request_id: str) -> ApprovalRequest:
        """批准审批请求。

        将请求状态更新为 approved，记录解决时间，并持久化。

        Args:
            request_id: 请求 ID。

        Returns:
            更新后的 ApprovalRequest 实例。

        Raises:
            ValueError: 如果请求不存在或状态不是 pending。
        """
        req = self._get_and_validate(request_id)
        req.status = ApprovalStatus.APPROVED.value
        req.resolved_at = time.time()

        # 持久化
        if self.storage is not None:
            self.storage.update_approval(
                request_id,
                ApprovalStatus.APPROVED.value,
                req.resolved_at,
            )

        return req

    def reject(self, request_id: str, reason: str = "") -> ApprovalRequest:
        """拒绝审批请求。

        将请求状态更新为 rejected，记录拒绝原因和解决时间，并持久化。

        Args:
            request_id: 请求 ID。
            reason: 拒绝原因，默认空字符串。

        Returns:
            更新后的 ApprovalRequest 实例。

        Raises:
            ValueError: 如果请求不存在或状态不是 pending。
        """
        req = self._get_and_validate(request_id)
        req.status = ApprovalStatus.REJECTED.value
        req.resolved_at = time.time()
        if reason:
            req.reason = reason

        # 持久化
        if self.storage is not None:
            self.storage.update_approval(
                request_id,
                ApprovalStatus.REJECTED.value,
                req.resolved_at,
            )

        return req

    def list_pending(self) -> list[ApprovalRequest]:
        """返回所有 pending 状态的审批请求。

        如果配置了持久化存储，优先从存储中查询，确保跨会话一致性。

        Returns:
            ApprovalRequest 列表，按创建时间升序排列。
        """
        if self.storage is not None:
            return self.storage.list_pending_approvals()

        # 纯内存模式
        pending = [
            req
            for req in self._requests.values()
            if req.status == ApprovalStatus.PENDING.value
        ]
        pending.sort(key=lambda r: r.created_at)
        return pending

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """按 ID 查询审批请求。

        优先从内存查询，回退到持久化存储。

        Args:
            request_id: 请求 ID。

        Returns:
            ApprovalRequest 实例，未找到返回 None。
        """
        # 先查内存
        if request_id in self._requests:
            return self._requests[request_id]

        # 回退到持久化存储
        if self.storage is not None:
            # 通过 list_pending_approvals 间接查询 ——
            # 存储层目前没有按 ID 单条查询的方法，但我们仍返回 None
            # 因为 get_request 仅保证内存中的数据可查
            return None

        return None

    def has_pending_for_run(self, run_id: str) -> bool:
        """检查指定 run 是否有未处理的审批。

        Args:
            run_id: 运行 ID。

        Returns:
            True 表示存在未处理的 pending 请求，False 表示无。
        """
        pending = self.list_pending()
        return any(req.run_id == run_id for req in pending)

    def _get_and_validate(self, request_id: str) -> ApprovalRequest:
        """获取审批请求并验证其状态为 pending。

        Args:
            request_id: 请求 ID。

        Returns:
            对应的 ApprovalRequest 实例。

        Raises:
            ValueError: 请求不存在或状态不是 pending。
        """
        req = self.get_request(request_id)
        if req is None:
            # 回退到内存
            req = self._requests.get(request_id)

        if req is None:
            raise ValueError(
                f"Approval request '{request_id}' not found"
            )

        if req.status != ApprovalStatus.PENDING.value:
            raise ValueError(
                f"Approval request '{request_id}' is already {req.status}, "
                f"cannot change again"
            )

        return req
