"""P2P Cache Network — integrates ResponseCache with P2P sharing.

Flow:
    get(url, prompt):
        1. Local ResponseCache hit → return immediately
        2. P2P network lookup → if found, cache locally + return
        3. Miss → return None (caller fetches from web)

    set(url, prompt, data):
        1. Save to local ResponseCache
        2. Broadcast to P2P network (privacy-sanitized)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional

from harvest.cache import ResponseCache
from harvest.p2p.node import P2PNode, P2PConfig
from harvest.p2p.error_handler import P2PErrorHandler

logger = logging.getLogger("harvest.p2p_cache")

# Max age for shared entries (7 days)
_MAX_ENTRY_AGE = 86400 * 7
# Max data payload size (500 KB)
_MAX_DATA_SIZE = 500 * 1024


class P2PCacheNetwork:
    """P2P layer on top of ResponseCache.

    Transparent: callers use get/set like a normal cache,
    but lookups also hit the P2P network on miss.
    """

    def __init__(
        self,
        local_cache: ResponseCache,
        config: Optional[P2PConfig] = None,
    ) -> None:
        self.local_cache = local_cache
        self.config = config or P2PConfig()
        self.node = P2PNode(self.config)
        self.error_handler = P2PErrorHandler()

        # Register P2P handlers
        self.node.on("cache_lookup", self._handle_lookup)
        self.node.on("cache_update", self._handle_update)

        # Metrics
        self._local_hits = 0
        self._p2p_hits = 0
        self._misses = 0
        self._broadcasts = 0
        self._p2p_errors = 0

        # Key→entry index for serving peer lookups
        self._key_index: Dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start P2P node."""
        if not self.config.enabled:
            logger.info("P2P cache disabled")
            return
        await self.node.start()
        logger.info(f"P2P cache started: {self.node.peer_id}")

    async def stop(self) -> None:
        """Stop P2P node."""
        await self.node.stop()

    # ------------------------------------------------------------------
    # Cache API (drop-in replacement for ResponseCache)
    # ------------------------------------------------------------------

    def get(self, url: str, prompt: str) -> Optional[Any]:
        """Get from cache (local only — sync for compatibility).

        For P2P-augmented lookup, use ``get_p2p`` instead.
        """
        key = self._make_key(url, prompt)
        return self.local_cache.get(key)

    async def get_p2p(self, url: str, prompt: str) -> Optional[Any]:
        """Get from cache (local + P2P network).

        Returns None on complete miss.
        """
        key = self._make_key(url, prompt)

        # 1. Local hit
        local = self.local_cache.get(key)
        if local is not None:
            self._local_hits += 1
            return local

        # 2. P2P lookup
        if self.config.enabled and self.error_handler.should_try():
            try:
                p2p_result = await self.node.lookup(key)
                if p2p_result is not None and self._verify_entry(p2p_result):
                    self._p2p_hits += 1
                    self.error_handler.record_success()
                    # Cache locally for future fast access
                    data = p2p_result.get("data")
                    if data is not None:
                        self.local_cache.set(key, data)
                        self._key_index[key] = p2p_result
                    return data
                self.error_handler.record_success()
            except Exception as e:
                self._p2p_errors += 1
                self.error_handler.record_error()
                logger.debug(f"P2P lookup failed: {e}")

        self._misses += 1
        return None

    def set(self, url: str, prompt: str, data: Any) -> None:
        """Save to local cache (sync for compatibility).

        For P2P broadcast, use ``set_p2p`` instead.
        """
        key = self._make_key(url, prompt)
        self.local_cache.set(key, data)

    async def set_p2p(self, url: str, prompt: str, data: Any) -> None:
        """Save to local cache + broadcast to P2P network."""
        key = self._make_key(url, prompt)
        self.local_cache.set(key, data)

        # Build shareable entry (privacy-sanitized)
        entry = self.node.sanitize_for_sharing(
            {
                "key": key,
                "url_hash": hashlib.sha256(url.encode()).hexdigest()[:16],
                "data": data,
                "timestamp": time.time(),
            }
        )
        self._key_index[key] = entry

        # Broadcast
        if self.config.enabled:
            try:
                await self.node.broadcast(entry)
                self._broadcasts += 1
            except Exception as e:
                logger.debug(f"P2P broadcast failed: {e}")

    # ------------------------------------------------------------------
    # P2P handlers (called by node)
    # ------------------------------------------------------------------

    async def _handle_lookup(self, key: str) -> Optional[dict]:
        """Serve a cache lookup from a remote peer."""
        # Check local cache first
        local = self.local_cache.get(key)
        if local is not None:
            return {"key": key, "data": local, "timestamp": time.time()}

        # Check our index
        if key in self._key_index:
            return self._key_index[key]

        return None

    async def _handle_update(self, update: dict) -> None:
        """Process gossip update from a peer."""
        entry = update.get("entry", {})
        if not self._verify_entry(entry):
            return

        key = entry.get("key")
        data = entry.get("data")
        if key and data is not None:
            # Cache locally (trust peer's data, verified by timestamp/size)
            self.local_cache.set(key, data)
            self._key_index[key] = entry
            logger.debug(f"P2P: cached entry for {key[:16]}...")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(url: str, prompt: str) -> str:
        """Deterministic cache key from URL + prompt."""
        raw = f"{url.strip().lower()}|{prompt.strip().lower()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _verify_entry(self, entry: dict) -> bool:
        """Verify a P2P entry is sane."""
        if not entry or "data" not in entry:
            return False

        # Not too old
        ts = entry.get("timestamp", 0)
        if time.time() - ts > _MAX_ENTRY_AGE:
            return False

        # Not too large
        try:
            if len(json.dumps(entry.get("data", {})).encode()) > _MAX_DATA_SIZE:
                return False
        except (TypeError, ValueError):
            return False

        return True

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """P2P cache statistics."""
        total = self._local_hits + self._p2p_hits + self._misses
        return {
            "enabled": self.config.enabled,
            "peer_id": self.node.peer_id,
            "connected_peers": len(self.node.peers),
            "local_hits": self._local_hits,
            "p2p_hits": self._p2p_hits,
            "misses": self._misses,
            "total_lookups": total,
            "p2p_hit_rate": round(self._p2p_hits / total, 3) if total > 0 else 0.0,
            "broadcasts": self._broadcasts,
            "p2p_errors": self._p2p_errors,
        }
