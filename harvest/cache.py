"""Cache — Lightweight TTL-based response cache for Harvest.

Usage:
    cache = ResponseCache(ttl_seconds=300)
    result = cache.get(url)
    if not result:
        result = await scrape(url)
        cache.set(url, result)
"""

import time
from typing import Any, Optional


class ResponseCache:
    """In-memory cache with time-to-live per entry."""

    def __init__(self, ttl_seconds: int = 300):
        self._ttl = ttl_seconds
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        entry = self._data.get(key)
        if entry is None:
            return None
        timestamp, value = entry
        if time.monotonic() - timestamp > self._ttl:
            del self._data[key]
            return None
        return value

    def set(self, key: str, value: Any):
        """Cache a value with current timestamp."""
        self._data[key] = (time.monotonic(), value)

    def invalidate(self, key: str):
        """Remove a specific entry."""
        self._data.pop(key, None)

    def clear(self):
        """Clear all cached entries."""
        self._data.clear()

    @property
    def size(self) -> int:
        return len(self._data)
