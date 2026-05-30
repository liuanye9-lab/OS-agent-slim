"""Feishu Notifier — V7.1 飞书审核通知。

使用飞书应用凭证发送审核通知消息。
凭证从环境变量 .env 读取（FEISHU_APP_ID, FEISHU_APP_SECRET）。

Usage:
    notifier = FeishuNotifier()
    notifier.send_review_notification(chat_id, patch_id, review_id, action)
"""

from __future__ import annotations

import logging
import os
import json
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """飞书消息通知客户端。

    使用 tenant_access_token 方式认证，发送审核通知。
    """

    def __init__(self) -> None:
        self._app_id = os.getenv("FEISHU_APP_ID", "")
        self._app_secret = os.getenv("FEISHU_APP_SECRET", "")
        self._chat_id = os.getenv("FEISHU_CHAT_ID", "")
        self._token: str | None = None
        self._configured = bool(self._app_id and self._app_secret)
        if self._configured:
            logger.info("FeishuNotifier configured: app_id=%s...", self._app_id[:8])
        else:
            logger.info("FeishuNotifier: 未配置（FEISHU_APP_ID/FEISHU_APP_SECRET 未设置）")

    @property
    def is_configured(self) -> bool:
        return self._configured and bool(self._chat_id)

    def _get_token(self) -> str:
        """获取 tenant_access_token（带缓存）。"""
        if self._token:
            return self._token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        data = json.dumps({
            "app_id": self._app_id,
            "app_secret": self._app_secret,
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                self._token = result.get("tenant_access_token", "")
                if self._token:
                    logger.debug("Feishu token obtained successfully")
                else:
                    logger.warning("Feishu token response: %s", result.get("msg", "unknown"))
        except urllib.error.URLError as e:
            logger.error("Feishu token request failed: %s", e)

        return self._token or ""

    def send_review_notification(
        self,
        patch_id: str,
        review_id: str,
        action: str,
        failure_mode: str = "",
        new_rule_preview: str = "",
        risk_level: str = "low",
    ) -> bool:
        """发送审核通知到飞书群。

        Args:
            patch_id: Patch ID。
            review_id: Review ID。
            action: "submitted" / "approved" / "rejected"。
            failure_mode: 失败模式。
            new_rule_preview: 新规则预览。
            risk_level: 风险等级。

        Returns:
            True 表示发送成功。
        """
        if not self.is_configured:
            logger.info("Feishu: 未配置 chat_id，跳过通知")
            return False

        token = self._get_token()
        if not token:
            logger.error("Feishu: 无法获取 access_token")
            return False

        action_zh = {"submitted": "🔔 待审核", "approved": "✅ 已通过", "rejected": "❌ 已拒绝"}
        label = action_zh.get(action, action)

        # 构建富文本消息
        content = json.dumps({
            "zh_cn": {
                "title": f"Skill Patch 审核 {label}",
                "content": [
                    [{"tag": "text", "text": f"Patch: {patch_id}"}],
                    [{"tag": "text", "text": f"Review: {review_id}"}],
                ]
                + ([{"tag": "text", "text": f"失败模式: {failure_mode}"}] if failure_mode else [])
                + ([{"tag": "text", "text": f"风险: {risk_level}"}] if risk_level else [])
                + ([{"tag": "text", "text": f"新规则: {new_rule_preview}"}] if new_rule_preview else []),
            }
        })

        body = json.dumps({
            "receive_id": self._chat_id,
            "msg_type": "interactive",
            "content": content,
        }).encode("utf-8")

        url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"

        try:
            req = urllib.request.Request(
                url, data=body,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Authorization": f"Bearer {token}",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                code = result.get("code", -1)
                if code == 0:
                    logger.info("Feishu notification sent: %s → %s", review_id, action)
                    return True
                else:
                    logger.warning("Feishu send failed: code=%s msg=%s", code, result.get("msg"))
                    return False
        except Exception as e:
            logger.error("Feishu notification error: %s", e)
            return False

    def send_text(self, text: str) -> bool:
        """发送纯文本消息到飞书群（用于简单通知）。"""
        if not self.is_configured:
            return False

        token = self._get_token()
        if not token:
            return False

        body = json.dumps({
            "receive_id": self._chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        }).encode("utf-8")

        url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
        try:
            req = urllib.request.Request(
                url, data=body,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Authorization": f"Bearer {token}",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                return result.get("code", -1) == 0
        except Exception as e:
            logger.error("Feishu text send error: %s", e)
            return False
