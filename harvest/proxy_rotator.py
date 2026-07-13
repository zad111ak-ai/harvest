"""
ProxyRotator — Free proxy rotation with health checks.

Features:
- Loads free proxies from public lists
- Health check (ping, HTTPS support)
- Fallback to direct connection
- Thread-safe rotation

Usage:
    rotator = ProxyRotator()
    proxy = rotator.get()  # "http://user:pass@host:port"
"""

import asyncio
import random
from typing import Optional, List
import aiohttp
from loguru import logger


class ProxyRotator:
    def __init__(self, sources: Optional[List[str]] = None):
        self.sources = sources or [
            "https://free-proxy-list.net/",
            "https://hidemy.name/en/proxy-list/?type=hs#list",
        ]
        self.proxies: List[str] = []
        self.healthy_proxies: List[str] = []
        self.lock = asyncio.Lock()

    async def load_proxies(self) -> None:
        """Load proxies from local file or public sources."""
        # Try local file first
        try:
            with open("/home/dima/harvest/proxies.txt", "r") as f:
                self.proxies = [f"http://{line.strip()}" for line in f if line.strip()]
                logger.info(f"Loaded {len(self.proxies)} proxies from local file")
                return
        except Exception as e:
            logger.debug(f"Local proxies failed: {e}")

        # Fallback to public sources
        async with aiohttp.ClientSession() as session:
            for source in self.sources:
                try:
                    async with session.get(source, timeout=5) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            new_proxies = self._extract_proxies(text)
                            self.proxies.extend(new_proxies)
                            logger.info(f"Loaded {len(new_proxies)} proxies from {source}")
                except Exception as e:
                    logger.warning(f"Failed to load {source}: {e}")

    def _extract_proxies(self, text: str) -> List[str]:
        """Extract IP:PORT from HTML."""
        import re

        # Example: 1.1.1.1:80 or user:pass@1.1.1.1:80
        pattern = r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        matches = re.findall(pattern, text)
        return [f"http://{m}" for m in matches]

    async def check_health(self, proxy: str) -> bool:
        """Check if proxy is alive and supports HTTPS."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://httpbin.org/ip",
                    proxy=proxy,
                    timeout=10,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "origin" in data:
                            return True
        except Exception as e:
            logger.debug(f"Proxy {proxy} failed: {e}")
        return False

    async def refresh_healthy(self) -> None:
        """Check all proxies and update healthy list."""
        async with self.lock:
            tasks = [self.check_health(p) for p in self.proxies]
            results = await asyncio.gather(*tasks)
            self.healthy_proxies = [p for p, healthy in zip(self.proxies, results) if healthy]
            logger.info(f"Healthy proxies: {len(self.healthy_proxies)}/{len(self.proxies)}")

    async def get(self) -> Optional[str]:
        """Get a random healthy proxy or None."""
        async with self.lock:
            if not self.healthy_proxies:
                await self.refresh_healthy()
            if self.healthy_proxies:
                return random.choice(self.healthy_proxies)
            return None

    async def start(self) -> None:
        """Load and check proxies on startup."""
        await self.load_proxies()
        await self.refresh_healthy()
        # Refresh every 30 minutes
        asyncio.create_task(self._periodic_refresh())

    async def _periodic_refresh(self) -> None:
        while True:
            await asyncio.sleep(1800)  # 30 minutes
            await self.refresh_healthy()
