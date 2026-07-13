"""ProxyRotator — Proxy rotation with pool support and domain affinity.

Features:
- User-provided proxy pools
- Environment variable HARVEST_PROXY_POOL (comma-separated)
- Round-robin selection
- Per-domain affinity (same proxy for same domain)
- Health checks

Usage:
    rotator = ProxyRotator(pool=["http://p1:8080", "http://p2:8080"])
    proxy = await rotator.get()
    proxy = await rotator.get_for_domain("ozon.ru")
"""

import asyncio
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import aiohttp
from loguru import logger


class ProxyRotator:
    def __init__(self, pool: Optional[list[str]] = None):
        self.pool = pool or self._load_from_env()
        self.healthy: list[str] = []
        self._index = 0
        self._domain_affinity: dict[str, str] = {}
        self.lock = asyncio.Lock()

    @staticmethod
    def _load_from_env() -> list[str]:
        raw = os.environ.get("HARVEST_PROXY_POOL", "")
        if raw:
            return [p.strip() for p in raw.split(",") if p.strip()]
        return []

    async def load_proxies(self):
        if self.pool:
            return
        try:
            proxy_file = Path.home() / "harvest" / "proxies.txt"
            with open(proxy_file) as f:
                self.pool = [f"http://{line.strip()}" for line in f if line.strip()]
                logger.info(f"Loaded {len(self.pool)} proxies from {proxy_file}")
        except FileNotFoundError:
            pass

    async def check_health(self, proxy: str) -> bool:
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://httpbin.org/ip", proxy=proxy) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return "origin" in data
        except Exception:
            pass
        return False

    async def refresh_healthy(self):
        if not self.pool:
            return
        async with self.lock:
            tasks = [self.check_health(p) for p in self.pool]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            self.healthy = [p for p, r in zip(self.pool, results) if r is True]
            logger.info(f"Healthy proxies: {len(self.healthy)}/{len(self.pool)}")

    async def get(self) -> Optional[str]:
        async with self.lock:
            if not self.healthy:
                return None
            proxy = self.healthy[self._index % len(self.healthy)]
            self._index += 1
            return proxy

    async def get_for_domain(self, domain: str) -> Optional[str]:
        if domain in self._domain_affinity:
            proxy = self._domain_affinity[domain]
            if proxy in self.healthy:
                return proxy
        new_proxy: Optional[str] = await self.get()
        if new_proxy:
            self._domain_affinity[domain] = new_proxy
        return new_proxy

    @staticmethod
    def get_domain(url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    async def start(self):
        await self.load_proxies()
        if self.pool:
            await self.refresh_healthy()
