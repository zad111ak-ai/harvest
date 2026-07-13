"""RateLimiter — Per-domain rate limiter for Harvest.

Usage:
    limiter = RateLimiter(max_per_minute=10, domain_limits={"ozon.ru": 2})
    async with limiter:
        await scrape(url)
"""

import asyncio
import time
from urllib.parse import urlparse


class _Bucket:
    """Simple token bucket."""

    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.tokens = float(max_per_minute)
        self._last_refill = time.monotonic()

    def refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        rate = self.max_per_minute / 60.0
        self.tokens = min(self.max_per_minute, self.tokens + elapsed * rate)
        self._last_refill = now


class RateLimiter:
    """Token-bucket rate limiter with per-domain support."""

    def __init__(
        self,
        max_per_minute: int = 10,
        domain_limits: dict[str, int] | None = None,
    ):
        self.max_per_minute = max_per_minute
        self.domain_limits = domain_limits or {}
        self._buckets: dict[str, _Bucket] = {}
        self._global = _Bucket(max_per_minute)
        self._lock = asyncio.Lock()

    def _get_domain(self, url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    def _get_bucket(self, url: str) -> tuple[_Bucket, _Bucket]:
        domain = self._get_domain(url)
        if domain not in self._buckets:
            limit = self.domain_limits.get(domain, self.max_per_minute)
            self._buckets[domain] = _Bucket(limit)
        return self._buckets[domain], self._global

    async def acquire(self, url: str = ""):
        """Wait until a token is available for the given URL's domain."""
        domain_bucket, global_bucket = self._get_bucket(url)
        while True:
            async with self._lock:
                domain_bucket.refill()
                global_bucket.refill()
                if domain_bucket.tokens >= 1 and global_bucket.tokens >= 1:
                    domain_bucket.tokens -= 1
                    global_bucket.tokens -= 1
                    return
            await asyncio.sleep(0.1)

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        pass
