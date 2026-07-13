"""Robots.txt checker — respect website crawling rules."""

from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import aiohttp


class RobotsChecker:
    """Check robots.txt rules before scraping."""

    def __init__(self, user_agent: str = "Harvest"):
        self.user_agent = user_agent
        self._cache: dict[str, RobotFileParser] = {}

    async def can_fetch(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        if base not in self._cache:
            robots_url = f"{base}/robots.txt"
            rp = RobotFileParser()
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(robots_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            rp.parse(text.splitlines())
                        else:
                            # No robots.txt = allow all
                            rp.parse(["User-agent: *", "Allow: /"])
            except Exception:
                # Can't fetch robots.txt = allow all
                rp.parse(["User-agent: *", "Allow: /"])

            self._cache[base] = rp

        return self._cache[base].can_fetch(self.user_agent, url)

    def get_crawl_delay(self, url: str) -> Optional[float]:
        """Get crawl-delay from robots.txt for this user-agent."""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base in self._cache:
            delay = self._cache[base].crawl_delay(self.user_agent)
            return float(delay) if delay else None
        return None
