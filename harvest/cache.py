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
    """In-memory cache with time-to-live per entry and max size limit."""

    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000):
        self._ttl = ttl_seconds
        self._max_size = max_size
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
        """Cache a value with current timestamp. Evicts oldest if over max_size."""
        if len(self._data) >= self._max_size:
            self._evict_expired()
        if len(self._data) >= self._max_size:
            self._evict_oldest()
        self._data[key] = (time.monotonic(), value)

    def _evict_expired(self):
        """Remove all expired entries."""
        now = time.monotonic()
        expired = [k for k, (ts, _) in self._data.items() if now - ts > self._ttl]
        for k in expired:
            del self._data[k]

    def _evict_oldest(self):
        """Remove the oldest entry to make room."""
        if not self._data:
            return
        oldest_key = min(self._data, key=lambda k: self._data[k][0])
        del self._data[oldest_key]

    def invalidate(self, key: str):
        """Remove a specific entry."""
        self._data.pop(key, None)

    def clear(self):
        """Clear all cached entries."""
        self._data.clear()

    @property
    def size(self) -> int:
        return len(self._data)
