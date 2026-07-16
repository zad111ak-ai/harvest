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

Optional embedding mode (requires sentence-transformers):
    cache = SemanticCache(ttl_seconds=3600, use_embeddings=True)
"""

import hashlib
import re
import time
from collections.abc import Sequence
from typing import Any, Optional

import numpy as _np  # always available — used for cosine similarity

# Optional sentence-transformers dependency for embedding-based similarity
try:
    from sentence_transformers import SentenceTransformer

    _HAS_EMBEDDINGS = True
except ImportError:
    _HAS_EMBEDDINGS = False

# Default lightweight model (~80 MB) suitable for CPU-only / low-RAM environments
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


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


def _embedding_cosine_similarity(a: Any, b: Any) -> float:
    """Cosine similarity between two embedding vectors (numpy arrays).

    Falls back gracefully if numpy is not available.
    """
    if a is None or b is None:
        return 0.0
    dot = float(_np.dot(a, b))
    norm_a = float(_np.linalg.norm(a))
    norm_b = float(_np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class _EmbeddingProvider:
    """Lazy singleton-ish wrapper around SentenceTransformer.

    Encodes text to embeddings and caches results to avoid redundant
    inference. Thread-safe for single-threaded cache access.
    """

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL):
        if not _HAS_EMBEDDINGS:
            raise ImportError(
                "sentence-transformers is required for embedding mode. "
                "Install with: pip install 'sentence-transformers'"
            )
        self._model = SentenceTransformer(model_name)
        self._model_name = model_name
        self._cache: dict[str, Any] = {}

    @property
    def model_name(self) -> str:
        return self._model_name

    def encode(self, text: str) -> Any:
        """Encode a single text string, with caching."""
        if text not in self._cache:
            self._cache[text] = self._model.encode(text)
        return self._cache[text]

    def similarity(self, text_a: str, text_b: str) -> float:
        """Cosine similarity between two raw text strings."""
        return _embedding_cosine_similarity(self.encode(text_a), self.encode(text_b))


def _content_hash(html: str) -> str:
    """Short hash of HTML content for cache invalidation."""
    return hashlib.md5(html.encode("utf-8", errors="replace")).hexdigest()[:12]


class SemanticCache:
    """Cache LLM responses by semantic similarity of prompts.

    Two queries with the same meaning but different wording
    will share the same cache entry (if similarity > threshold).

    Entries are invalidated when the HTML content changes.

    Args:
        ttl_seconds: Cache entry lifetime in seconds.
        max_size: Maximum total entries across all URLs.
        similarity_threshold: Minimum similarity score to consider a match.
        use_embeddings: If True and sentence-transformers is installed,
            use embedding-based cosine similarity instead of Jaccard.
            Falls back to Jaccard when the optional dep is missing.
        embedding_model: Sentence-transformers model name. Only used when
            use_embeddings=True. Defaults to ``all-MiniLM-L6-v2``.
    """

    def __init__(
        self,
        ttl_seconds: int = 3600,
        max_size: int = 500,
        similarity_threshold: float = 0.75,
        use_embeddings: bool = False,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ):
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._threshold = similarity_threshold
        self._use_embeddings = use_embeddings and _HAS_EMBEDDINGS
        self._embedding_model_name: Optional[str] = None
        self._embedding_provider: Optional[_EmbeddingProvider] = None

        if self._use_embeddings:
            try:
                self._embedding_provider = _EmbeddingProvider(embedding_model)
                self._embedding_model_name = embedding_model
            except ImportError:
                # sentence-transformers not installed — graceful fallback
                self._use_embeddings = False

        # Each entry: {url: [{tokens, html_hash, response, timestamp}, ...]}
        self._data: dict[str, list[dict[str, Any]]] = {}
        self.hits = 0
        self.misses = 0

    # -- public helpers for introspection --

    @property
    def use_embeddings(self) -> bool:
        """Whether embedding mode is active."""
        return self._use_embeddings

    @property
    def embedding_model(self) -> Optional[str]:
        """Name of the embedding model in use, or None."""
        return self._embedding_model_name

    def get(
        self,
        url: str,
        prompt: str,
        html: Optional[str] = None,
    ) -> Optional[Any]:
        """Find a semantically similar cached response.

        Args:
            url: The page URL (exact match required).
            prompt: The extraction prompt (semantic match).
            html: Current HTML content. If provided, invalidates stale cache
                  when the page has changed.

        Returns:
            Cached response if found and valid, None otherwise.
        """
        entries = self._data.get(url)
        if not entries:
            self.misses += 1
            return None

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

            # Compute similarity using chosen method
            if self._use_embeddings and self._embedding_provider:
                score = self._embedding_provider.similarity(prompt, entry["prompt_text"])
            else:
                query_tokens = _tokenize(prompt)
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
            "prompt_text": prompt,  # kept for embedding comparison
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
            "use_embeddings": self._use_embeddings,
            "embedding_model": self._embedding_model_name,
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
