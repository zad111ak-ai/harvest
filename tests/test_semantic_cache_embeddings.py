"""
Tests for optional sentence-transformers embeddings in SemanticCache.

Covers: embedding creation, cosine similarity, fallback when the dep is
missing, similarity threshold behaviour, stats reporting, and pickle
round-tripping with embeddings.

Run: python3 -m pytest tests/test_semantic_cache_embeddings.py -v
"""

import pickle

import pytest
import numpy as np

# ---------------------------------------------------------------------------
# Determine whether sentence-transformers is actually available
# ---------------------------------------------------------------------------
try:
    from sentence_transformers import SentenceTransformer  # noqa: F401

    _HAS_ST = True
except ImportError:
    _HAS_ST = False

requires_embeddings = pytest.mark.skipif(
    not _HAS_ST,
    reason="sentence-transformers not installed",
)

# ---------------------------------------------------------------------------
# Module-level helpers we import from the production code
# ---------------------------------------------------------------------------
from harvest.semantic_cache import (  # noqa: E402
    _EmbeddingProvider,
    _embedding_cosine_similarity,
    SemanticCache,
    DEFAULT_EMBEDDING_MODEL,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def embedding_provider():
    """Create a single _EmbeddingProvider for the whole module (model loads once)."""
    return _EmbeddingProvider(DEFAULT_EMBEDDING_MODEL)


@pytest.fixture()
def embedding_cache():
    """A SemanticCache with embedding mode enabled."""
    return SemanticCache(
        ttl_seconds=300,
        similarity_threshold=0.5,
        use_embeddings=True,
    )


@pytest.fixture()
def jaccard_cache():
    """A plain Jaccard-mode SemanticCache (default)."""
    return SemanticCache(ttl_seconds=300, similarity_threshold=0.5)


# ===========================================================================
# Test 1 – Embedding creation
# ===========================================================================
@requires_embeddings
def test_embedding_provider_creates_vectors(embedding_provider):
    """_EmbeddingProvider.encode() should return a finite numpy vector."""
    vec = embedding_provider.encode("Hello world")
    assert isinstance(vec, np.ndarray)
    assert vec.ndim == 1
    assert vec.shape[0] > 0
    assert np.all(np.isfinite(vec))


# ===========================================================================
# Test 2 – Cosine similarity between embeddings
# ===========================================================================
@requires_embeddings
def test_embedding_cosine_similarity_similar(embedding_provider):
    """Similar sentences should produce high cosine similarity (>0.7)."""
    score = embedding_provider.similarity(
        "Get all product prices",
        "Extract all product prices",
    )
    assert score > 0.7, f"Expected high similarity, got {score}"


@requires_embeddings
def test_embedding_cosine_similarity_dissimilar(embedding_provider):
    """Very different sentences should produce low cosine similarity (<0.5)."""
    score = embedding_provider.similarity(
        "Get all product prices",
        "Tell me a joke about chickens",
    )
    assert score < 0.5, f"Expected low similarity, got {score}"


# ===========================================================================
# Test 3 – Cosine similarity on raw vectors (unit-level)
# ===========================================================================
def test_embedding_cosine_similarity_identical_vectors():
    """Identical vectors should have similarity of 1.0."""
    v = np.array([1.0, 2.0, 3.0])
    assert _embedding_cosine_similarity(v, v) == pytest.approx(1.0)


def test_embedding_cosine_similarity_orthogonal_vectors():
    """Orthogonal vectors should have similarity of 0.0."""
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert _embedding_cosine_similarity(a, b) == pytest.approx(0.0)


def test_embedding_cosine_similarity_none_vectors():
    """None inputs should return 0.0."""
    assert _embedding_cosine_similarity(None, None) == 0.0
    assert _embedding_cosine_similarity(np.array([1.0]), None) == 0.0


# ===========================================================================
# Test 4 – Fallback when sentence-transformers is not installed
# ===========================================================================
def test_fallback_when_no_sentence_transformers():
    """When sentence_transformers import fails, use_embeddings is silently off."""
    # Save original state
    import harvest.semantic_cache as sc_mod

    original_has = sc_mod._HAS_EMBEDDINGS

    try:
        # Fake the import being unavailable
        sc_mod._HAS_EMBEDDINGS = False

        cache = SemanticCache(use_embeddings=True)
        assert cache.use_embeddings is False
        assert cache.embedding_model is None
    finally:
        # Restore
        sc_mod._HAS_EMBEDDINGS = original_has


def test_fallback_cache_still_works_jaccard(jaccard_cache):
    """Jaccard fallback should still find semantically similar prompts."""
    jaccard_cache.set(
        "https://example.com",
        "Extract all product prices",
        "<html></html>",
        {"prices": [10]},
    )
    result = jaccard_cache.get(
        "https://example.com",
        "Get all product prices",
        "<html></html>",
    )
    assert result is not None
    assert result["prices"] == [10]


# ===========================================================================
# Test 5 – Similarity threshold with embeddings
# ===========================================================================
@requires_embeddings
def test_embedding_threshold_high_blocks_match():
    """A very high threshold should block a mildly similar match."""
    cache = SemanticCache(
        similarity_threshold=0.99,  # almost-perfect match required
        use_embeddings=True,
    )
    cache.set(
        "https://example.com",
        "Extract all product prices",
        "<html></html>",
        {"prices": [10]},
    )
    # Different wording — high threshold should block
    cache.get(
        "https://example.com",
        "Get all product prices",
        "<html></html>",
    )
    # The threshold is so high (0.99) that a paraphrase should NOT match
    # unless the model sees them as almost identical.
    # We check that the mechanism works: no hit counted
    assert cache.hits == 0


@requires_embeddings
def test_embedding_threshold_low_allows_match():
    """A low threshold should allow a loosely similar match."""
    cache = SemanticCache(
        similarity_threshold=0.3,  # very permissive
        use_embeddings=True,
    )
    cache.set(
        "https://example.com",
        "Extract all product prices",
        "<html></html>",
        {"prices": [10]},
    )
    result = cache.get(
        "https://example.com",
        "Get all product prices",
        "<html></html>",
    )
    assert result is not None


# ===========================================================================
# Test 6 – Stats include embedding mode
# ===========================================================================
@requires_embeddings
def test_stats_include_embedding_mode(embedding_cache):
    """stats() should report use_embeddings and embedding_model."""
    embedding_cache.set("https://a.com", "test prompt", "<html></html>", "ok")
    embedding_cache.get("https://a.com", "test prompt", "<html></html>")
    stats = embedding_cache.stats()

    assert "use_embeddings" in stats
    assert stats["use_embeddings"] is True
    assert "embedding_model" in stats
    assert stats["embedding_model"] == DEFAULT_EMBEDDING_MODEL


def test_stats_jaccard_mode(jaccard_cache):
    """stats() should report use_embeddings=False when embeddings are off."""
    stats = jaccard_cache.stats()
    assert stats["use_embeddings"] is False
    assert stats["embedding_model"] is None


# ===========================================================================
# Test 7 – Pickle round-trip with embeddings
# ===========================================================================
@requires_embeddings
def test_pickle_unpickle_with_embeddings(embedding_cache):
    """Cache entries should survive pickle/unpickle and remain usable."""
    embedding_cache.set(
        "https://example.com",
        "Extract all product prices",
        "<html></html>",
        {"prices": [10]},
    )

    # Pickle the cache's internal data (not the provider)
    raw = pickle.dumps(embedding_cache._data)
    restored_data = pickle.loads(raw)

    # Verify the restored data can be used
    assert "https://example.com" in restored_data
    entry = restored_data["https://example.com"][0]
    assert entry["tokens"] == ["extract", "all", "product", "prices"]
    assert entry["prompt_text"] == "Extract all product prices"
    assert entry["response"] == {"prices": [10]}


def test_pickle_unpickle_jaccard_mode(jaccard_cache):
    """Jaccard mode cache entries should also survive pickle."""
    jaccard_cache.set(
        "https://example.com",
        "Get prices",
        "<html></html>",
        "result",
    )
    raw = pickle.dumps(jaccard_cache._data)
    restored = pickle.loads(raw)
    assert restored["https://example.com"][0]["tokens"] == ["get", "prices"]


# ===========================================================================
# Test 8 – Full embedding round-trip: set → get with semantic match
# ===========================================================================
@requires_embeddings
def test_embedding_full_cache_round_trip():
    """Full cycle: store with one wording, retrieve with a different wording."""
    cache = SemanticCache(
        similarity_threshold=0.5,
        use_embeddings=True,
    )
    cache.set(
        "https://shop.com",
        "List all available product prices on the page",
        "<html><div class='price'>$10</div></html>",
        {"prices": [10]},
    )
    # Different wording but same meaning
    result = cache.get(
        "https://shop.com",
        "Show me every price for products listed",
        "<html><div class='price'>$10</div></html>",
    )
    assert result is not None
    assert result["prices"] == [10]
    assert cache.hits == 1


# ===========================================================================
# Test 9 – Embedding mode respects HTML invalidation
# ===========================================================================
@requires_embeddings
def test_embedding_html_invalidation():
    """Cached entry should be invalidated when HTML content changes."""
    cache = SemanticCache(
        similarity_threshold=0.5,
        use_embeddings=True,
    )
    cache.set(
        "https://example.com",
        "Get all prices",
        "<html>v1</html>",
        {"prices": [10]},
    )
    # Same prompt but different HTML → should miss
    result = cache.get(
        "https://example.com",
        "Get all prices",
        "<html>v2</html>",
    )
    assert result is None
