"""RateLimiter — Simple client-side rate limiter for Harvest.

Usage:
    limiter = RateLimiter(max_per_minute=10)
    async with limiter:
        await scrape(url)
"""

import asyncio
import time


class RateLimiter:
    """Token-bucket rate limiter that delays requests to stay under a per-minute cap."""

    def __init__(self, max_per_minute: int = 10):
        self.max_per_minute = max_per_minute
        self._tokens = float(max_per_minute)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a token is available."""
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
            # Wait before retrying
            await asyncio.sleep(0.1)

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        rate = self.max_per_minute / 60.0
        self._tokens = min(self.max_per_minute, self._tokens + elapsed * rate)
        self._last_refill = now

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        pass
