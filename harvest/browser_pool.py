"""
Browser Pool — Pre-warmed browser pool for instant scraping.

Instead of creating a new browser each time, maintain warm browsers
ready for immediate use. Reduces cold-start from ~5s to ~0s.

Usage:
    pool = BrowserPool(warm_count=3)
    await pool.start()
    async with pool.acquire() as browser:
        result = await browser.fetch(url)
"""

import asyncio
import time
from collections import deque
from typing import Optional
from contextlib import asynccontextmanager

from .browser import BrowserSession


class BrowserPool:
    """Pre-warmed browser pool for instant scraping.

    Maintains a pool of ready-to-use BrowserSession instances.
    When a browser is requested, it's instantly available from the warm pool.
    When returned, it goes back to the pool for reuse.

    Architecture:
    - warm: Ready to use immediately (hot)
    - active: Currently in use by a scraper
    - stats: Track pool performance
    """

    def __init__(
        self,
        warm_count: int = 3,
        proxy: Optional[str] = None,
        headless: bool = True,
        timeout: int = 60000,
        solve_cloudflare: bool = True,
        max_pages: int = 3,
    ):
        self.warm_count = warm_count
        self.proxy = proxy
        self.headless = headless
        self.timeout = timeout
        self.solve_cloudflare = solve_cloudflare
        self.max_pages = max_pages

        self._warm: deque[BrowserSession] = deque()
        self._active: set[BrowserSession] = set()
        self._lock = asyncio.Lock()
        self._started = False

        # Stats
        self.stats = {
            "total_requests": 0,
            "pool_hits": 0,
            "pool_misses": 0,
            "total_wait_ms": 0,
            "browsers_created": 0,
            "browsers_reused": 0,
        }

    async def start(self) -> None:
        """Pre-warm the pool with browsers."""
        if self._started:
            return

        print(f"🏊 Pre-warming {self.warm_count} browsers...")
        start = time.monotonic()

        tasks = [self._create_browser() for _ in range(self.warm_count)]
        browsers = await asyncio.gather(*tasks, return_exceptions=True)

        for b in browsers:
            if isinstance(b, BrowserSession):
                self._warm.append(b)
                self.stats["browsers_created"] += 1

        elapsed = time.monotonic() - start
        self._started = True
        print(f"✅ Pool ready: {len(self._warm)} browsers warmed in {elapsed:.1f}s")

    async def stop(self) -> None:
        """Close all browsers in the pool."""
        async with self._lock:
            while self._warm:
                browser = self._warm.popleft()
                await browser.close()
            for browser in list(self._active):
                await browser.close()
            self._active.clear()
            self._started = False

    async def _create_browser(self) -> BrowserSession:
        """Create a single browser session."""
        return await BrowserSession.create(
            proxy=self.proxy,
            headless=self.headless,
            timeout=self.timeout,
            solve_cloudflare=self.solve_cloudflare,
            max_pages=self.max_pages,
        )

    @asynccontextmanager
    async def acquire(self):
        """Acquire a browser from the pool.

        Usage:
            async with pool.acquire() as browser:
                result = await browser.fetch(url)
        """
        browser = await self._get_browser()
        try:
            yield browser
        finally:
            await self._return_browser(browser)

    async def _get_browser(self) -> BrowserSession:
        """Get a browser from the pool or create a new one."""
        self.stats["total_requests"] += 1
        start = time.monotonic()

        async with self._lock:
            if self._warm:
                browser = self._warm.popleft()
                self.stats["pool_hits"] += 1
                self.stats["browsers_reused"] += 1
            else:
                self.stats["pool_misses"] += 1
                self.stats["browsers_created"] += 1
                browser = await self._create_browser()

            self._active.add(browser)

        elapsed_ms = (time.monotonic() - start) * 1000
        self.stats["total_wait_ms"] += elapsed_ms
        return browser

    async def _return_browser(self, browser: BrowserSession) -> None:
        """Return a browser to the warm pool."""
        async with self._lock:
            self._active.discard(browser)

            if len(self._warm) < self.warm_count:
                self._warm.append(browser)
            else:
                # Pool is full, close the extra browser
                await browser.close()

    async def warm_up(self, count: Optional[int] = None) -> None:
        """Add more warm browsers to the pool."""
        count = count or self.warm_count
        async with self._lock:
            current = len(self._warm)
            to_add = max(0, count - current)

        if to_add > 0:
            tasks = [self._create_browser() for _ in range(to_add)]
            browsers = await asyncio.gather(*tasks, return_exceptions=True)
            async with self._lock:
                for b in browsers:
                    if isinstance(b, BrowserSession):
                        self._warm.append(b)

    def get_stats(self) -> dict:
        """Get pool statistics."""
        total = self.stats["total_requests"]
        hits = self.stats["pool_hits"]
        return {
            **self.stats,
            "warm_available": len(self._warm),
            "active": len(self._active),
            "hit_rate": f"{hits / total * 100:.1f}%" if total > 0 else "N/A",
            "avg_wait_ms": (f"{self.stats['total_wait_ms'] / total:.1f}" if total > 0 else "N/A"),
        }


# Global pool instance (lazy init)
_pool: Optional[BrowserPool] = None


async def get_pool(**kwargs) -> BrowserPool:
    """Get or create the global browser pool."""
    global _pool
    if _pool is None:
        _pool = BrowserPool(**kwargs)
        await _pool.start()
    return _pool
