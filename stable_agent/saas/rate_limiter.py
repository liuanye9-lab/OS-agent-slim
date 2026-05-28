"""速率限制模块 (SaaS v1.5)。

基于滑动窗口的 API 速率限制，按 API Key 或 IP 限流。

规则：
- Free: 10 req/min per key
- Pro: 60 req/min
- Team: 300 req/min
- Enterprise: 无限制

用法::

    limiter = RateLimiter()
    ok, retry_after = limiter.check("ws_xxx", "free")
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Any

# 套餐对应的每分钟请求限制
TIER_LIMITS: dict[str, int] = {
    "free": 10,
    "pro": 60,
    "team": 300,
    "enterprise": -1,  # 无限制
}

WINDOW_SECONDS: int = 60


class RateLimiter:
    """简单滑动窗口速率限制器（内存实现）。"""

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock: Lock = Lock()

    def check(self, key: str, tier: str = "free") -> tuple[bool, float]:
        """检查是否允许此请求。

        Args:
            key: 限流键（通常是 workspace_id 或 api_key_id）。
            tier: 套餐层级。

        Returns:
            (是否允许, 重试等待秒数)
        """
        limit = TIER_LIMITS.get(tier, 10)
        if limit < 0:
            return True, 0  # 无限制

        now = time.time()
        with self._lock:
            # 清理过期记录
            cutoff = now - WINDOW_SECONDS
            self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]

            if len(self._buckets[key]) >= limit:
                oldest = self._buckets[key][0]
                retry_after = round(oldest + WINDOW_SECONDS - now + 0.1, 1)
                return False, max(0, retry_after)

            self._buckets[key].append(now)
            return True, 0

    def reset(self, key: str) -> None:
        """重置指定 key 的限流计数。"""
        with self._lock:
            self._buckets.pop(key, None)
