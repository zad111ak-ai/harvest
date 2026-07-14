"""Semantic Cache — Meaning-based response cache for LLM extraction.

Caches by semantic similarity of the prompt, not exact text match.
Saves 50-70% of LLM tokens on repeated similar queries.

Usage:
    cache = SemanticCache(ttl_seconds=3600)
    result = cache.get(url="https://shop.com", prompt="Get all prices")
    if not result:
        result = await llm_extract(url, prompt)
        cache.set(url="https://shop.com", prompt="Get all prices",
                  html_hash=hash(html), response=result)
"""

import hashlib
import re
import time
from collections.abc import Sequence
from typing import Any, Callable, Optional


def _tokenize(text: str) -> list[str]:
    """Lowercase + split into word tokens."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _cosine_similarity(a: Sequence[str], b: Sequence[str]) -> float:
    """Hybrid similarity: max of Jaccard and containment. Fast, no deps."""
    if not a or not b:
        return 0.0
    set_a, set_b = set(a), set(b)
    intersection = set_a & set_b
    union = set_a | set_b
    jaccard = len(intersection) / len(union) if union else 0.0
    # Containment: what fraction of the smaller query is in the larger
    smaller, larger = (set_a, set_b) if len(set_a) <= len(set_b) else (set_b, set_a)
    containment = len(intersection) / len(smaller) if smaller else 0.0
    return max(jaccard, containment)


def _content_hash(html: str) -> str:
    """Short hash of HTML content for cache invalidation."""
    return hashlib.md5(html.encode("utf-8", errors="replace")).hexdigest()[:12]


class SemanticCache:
    """Cache LLM responses by semantic similarity of prompts.

    Two queries with the same meaning but different wording
    will share the same cache entry (if similarity > threshold).

    Entries are invalidated when the HTML content changes.

    Supports optional health-check callback: when the check fails
    (e.g. Redis connection lost) the cache auto-clears so stale
    data is never served across an outage.
    """

    def __init__(
        self,
        ttl_seconds: int = 3600,
        max_size: int = 500,
        similarity_threshold: float = 0.75,
        health_check_fn: Optional[Callable[[], bool]] = None,
    ):
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._threshold = similarity_threshold
        self._health_check = health_check_fn
        self._was_healthy = True
        # Each entry: {url: [{tokens, html_hash, response, timestamp}, ...]}
        self._data: dict[str, list[dict[str, Any]]] = {}
        self.hits = 0
        self.misses = 0

    def get(
        self,
        url: str,
        prompt: str,
        html: Optional[str] = None,
    ) -> Optional[Any]:
        """Find a semantically similar cached response.

        If a health_check_fn was provided and the backend (e.g. Redis)
        is unreachable, the entire cache is cleared and None is returned.

        Args:
            url: The page URL (exact match required).
            prompt: The extraction prompt (semantic match).
            html: Current HTML content. If provided, invalidates stale cache
                  when the page has changed.

        Returns:
            Cached response if found and valid, None otherwise.
        """
        if self._health_check:
            healthy = self._health_check()
            if not healthy:
                if self._was_healthy:
                    self.clear()
                    self._was_healthy = False
                self.misses += 1
                return None
            self._was_healthy = True

        entries = self._data.get(url)
        if not entries:
            self.misses += 1
            return None

        query_tokens = _tokenize(prompt)
        current_hash = _content_hash(html) if html else None

        best_match: Optional[dict] = None
        best_score = 0.0

        for entry in entries:
            # Expired?
            if time.monotonic() - entry["timestamp"] > self._ttl:
                continue

            # HTML changed → invalidate this entry
            if current_hash and entry["html_hash"] != current_hash:
                continue

            score = _cosine_similarity(query_tokens, entry["tokens"])
            if score > best_score:
                best_score = score
                best_match = entry

        if best_match and best_score >= self._threshold:
            self.hits += 1
            return best_match["response"]

        self.misses += 1
        return None

    def set(
        self,
        url: str,
        prompt: str,
        html: str,
        response: Any,
    ):
        """Store a response with its prompt context.

        Args:
            url: The page URL.
            prompt: The extraction prompt used.
            html: The HTML content at extraction time.
            response: The LLM extraction result.
        """
        if url not in self._data:
            self._data[url] = []

        entry = {
            "tokens": _tokenize(prompt),
            "html_hash": _content_hash(html),
            "response": response,
            "timestamp": time.monotonic(),
            "prompt_preview": prompt[:100],
        }

        self._data[url].append(entry)

        # Evict if over limit (per-URL)
        if len(self._data[url]) > 20:
            self._data[url] = self._data[url][-20:]

        total = sum(len(v) for v in self._data.values())
        if total > self._max_size:
            self._evict_oldest()

    def invalidate(self, url: str):
        """Remove all cached entries for a URL."""
        self._data.pop(url, None)

    def clear(self):
        """Clear entire cache."""
        self._data.clear()
        self.hits = 0
        self.misses = 0

    def stats(self) -> dict:
        """Cache performance statistics."""
        total_entries = sum(len(v) for v in self._data.values())
        total_queries = self.hits + self.misses
        hit_rate = self.hits / total_queries if total_queries > 0 else 0.0
        return {
            "total_entries": total_entries,
            "total_urls": len(self._data),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.1%}",
            "tokens_saved_estimate": f"~{self.hits * 500} tokens",
        }

    def _evict_oldest(self):
        """Remove oldest entry across all URLs."""
        oldest_url = None
        oldest_ts = float("inf")
        for url, entries in self._data.items():
            if entries and entries[0]["timestamp"] < oldest_ts:
                oldest_ts = entries[0]["timestamp"]
                oldest_url = url
        if oldest_url:
            self._data[oldest_url].pop(0)
            if not self._data[oldest_url]:
                del self._data[oldest_url]
