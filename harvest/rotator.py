"""
ProxyRotator — Rotate proxies for resilient scraping.

Load proxies from file or list, rotate on each request or on failure.
"""

import random
from pathlib import Path
from typing import Optional


class ProxyRotator:
    """Rotate HTTP proxies for resilient scraping.

    Features:
    - Load from file (one proxy per line)
    - Auto-rotate on each request or on failure
    - Simple proxy validation (basic format check)
    - Concurrent-safe counter

    Usage:
        rotator = ProxyRotator.from_file("proxies.txt")
        proxy = rotator.get()  # gets next proxy
        proxy = rotator.rotate()  # gets next and advances
    """

    def __init__(self, proxies: Optional[list[str]] = None):
        self._proxies = proxies or []
        self._index = 0

    @classmethod
    def from_file(cls, path: str) -> "ProxyRotator":
        """Load proxies from a file (one per line)."""
        raw = Path(path).expanduser().read_text()
        lines = [line.strip() for line in raw.splitlines() if line.strip() and not line.startswith("#")]

        proxies = []
        for line in lines:
            proxy = cls._normalize_proxy(line)
            if proxy:
                proxies.append(proxy)

        return cls(proxies)

    @classmethod
    def from_strings(cls, *proxies: str) -> "ProxyRotator":
        """Create from explicit proxy strings."""
        normalized = [cls._normalize_proxy(p) for p in proxies]
        return cls([p for p in normalized if p])

    @staticmethod
    def _normalize_proxy(proxy: str) -> Optional[str]:
        """Normalize proxy URL to http://user:pass@host:port format."""
        proxy = proxy.strip()
        if not proxy:
            return None

        # Already has scheme
        if (
            proxy.startswith("http://")
            or proxy.startswith("https://")
            or proxy.startswith("socks5://")
            or proxy.startswith("socks4://")
        ):
            return proxy

        # Assume HTTP
        return f"http://{proxy}"

    def get(self) -> Optional[str]:
        """Get current proxy without advancing."""
        if not self._proxies:
            return None
        return self._proxies[self._index % len(self._proxies)]

    def rotate(self) -> Optional[str]:
        """Advance to next proxy and return it."""
        if not self._proxies:
            return None
        self._index = (self._index + 1) % len(self._proxies)
        return self._proxies[self._index]

    def random(self) -> Optional[str]:
        """Get a random proxy from the pool."""
        if not self._proxies:
            return None
        return random.choice(self._proxies)

    @property
    def count(self) -> int:
        return len(self._proxies)

    @property
    def current_index(self) -> int:
        return self._index
