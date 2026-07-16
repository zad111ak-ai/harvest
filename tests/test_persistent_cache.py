"""
Tests for PersistentCache (SQLite-backed disk cache).

Run: python3 -m pytest tests/test_persistent_cache.py -v
"""

import os
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from harvest.persistent_cache import PersistentCache


# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db(tmp_path):
    """Return a PersistentCache pointing at a temporary DB."""
    db = str(tmp_path / "test_cache.db")
    cache = PersistentCache(ttl_seconds=5, max_size=10, db_path=db)
    yield cache


@pytest.fixture
def tmp_db_long_ttl(tmp_path):
    """Cache with a generous TTL for persistence tests."""
    db = str(tmp_path / "persist_test.db")
    cache = PersistentCache(ttl_seconds=3600, max_size=100, db_path=db)
    yield cache


# ── 1. set / get basics ──────────────────────────────────────────────


def test_set_get_simple(tmp_db):
    """Setting a value and getting it back should work for basic types."""
    tmp_db.set("key1", "hello")
    assert tmp_db.get("key1") == "hello"

    tmp_db.set("key2", 42)
    assert tmp_db.get("key2") == 42

    tmp_db.set("key3", {"nested": [1, 2, 3]})
    assert tmp_db.get("key3") == {"nested": [1, 2, 3]}


def test_get_missing_key_returns_none(tmp_db):
    """Getting a non-existent key should return None."""
    assert tmp_db.get("does_not_exist") is None


def test_set_overwrites(tmp_db):
    """Setting the same key twice should overwrite."""
    tmp_db.set("k", "first")
    tmp_db.set("k", "second")
    assert tmp_db.get("k") == "second"
    assert tmp_db.size == 1


# ── 2. TTL expiry ────────────────────────────────────────────────────


def test_ttl_expiry(tmp_path):
    """Entries should disappear after their TTL."""
    db = str(tmp_path / "ttl_test.db")
    cache = PersistentCache(ttl_seconds=1, max_size=10, db_path=db)

    cache.set("expiring", "value")
    assert cache.get("expiring") == "value"

    # Wait for TTL
    time.sleep(1.1)
    assert cache.get("expiring") is None


def test_ttl_no_expiry_for_fresh_entries(tmp_path):
    """Fresh entries should not be expired."""
    db = str(tmp_path / "fresh.db")
    cache = PersistentCache(ttl_seconds=3600, max_size=10, db_path=db)
    cache.set("fresh", "data")
    # Immediately check — should be there
    assert cache.get("fresh") == "data"


# ── 3. invalidate ────────────────────────────────────────────────────


def test_invalidate_removes_entry(tmp_db):
    """invalidate() should remove a specific key."""
    tmp_db.set("a", 1)
    tmp_db.set("b", 2)
    assert tmp_db.size == 2

    tmp_db.invalidate("a")
    assert tmp_db.get("a") is None
    assert tmp_db.get("b") == 2
    assert tmp_db.size == 1


def test_invalidate_nonexistent_is_noop(tmp_db):
    """Invalidating a key that doesn't exist should not raise."""
    tmp_db.invalidate("ghost")
    assert tmp_db.size == 0


# ── 4. clear ─────────────────────────────────────────────────────────


def test_clear_removes_all(tmp_db):
    """clear() should remove all entries."""
    for i in range(5):
        tmp_db.set(f"item{i}", i)
    assert tmp_db.size == 5

    tmp_db.clear()
    assert tmp_db.size == 0
    assert tmp_db.get("item0") is None


# ── 5. stats ─────────────────────────────────────────────────────────


def test_stats(tmp_db):
    """stats() should return correct metadata."""
    tmp_db.set("x", 10)
    tmp_db.set("y", 20)
    s = tmp_db.stats()

    assert s["total_entries"] == 2
    assert s["max_size"] == 10
    assert s["ttl_seconds"] == 5
    assert "db_path" in s
    assert s["oldest_entry_age"] is not None
    assert s["newest_entry_age"] is not None
    assert s["oldest_entry_age"] >= 0
    assert s["newest_entry_age"] <= s["oldest_entry_age"]


def test_stats_empty_cache(tmp_db):
    """stats() on an empty cache should still work."""
    s = tmp_db.stats()
    assert s["total_entries"] == 0
    assert s["oldest_entry_age"] is None


# ── 6. max_size eviction ─────────────────────────────────────────────


def test_max_size_eviction(tmp_path):
    """Adding more than max_size entries should evict oldest."""
    db = str(tmp_path / "evict_test.db")
    cache = PersistentCache(ttl_seconds=3600, max_size=5, db_path=db)

    for i in range(5):
        cache.set(f"item{i}", i)

    assert cache.size == 5

    # Adding a 6th item should trigger eviction of item0
    cache.set("item5", 5)
    assert cache.size == 5
    assert cache.get("item0") is None  # evicted
    assert cache.get("item5") == 5  # new


def test_max_size_evicts_multiple_when_needed(tmp_path):
    """Adding several items at once should evict enough oldest entries."""
    db = str(tmp_path / "multi_evict.db")
    cache = PersistentCache(ttl_seconds=3600, max_size=3, db_path=db)

    for i in range(3):
        cache.set(f"old{i}", i)

    # Add 2 more — should evict the 2 oldest
    cache.set("new0", "a")
    cache.set("new1", "b")

    assert cache.size == 3
    assert cache.get("old0") is None
    assert cache.get("old1") is None
    assert cache.get("new0") == "a"
    assert cache.get("new1") == "b"


# ── 7. concurrent access ─────────────────────────────────────────────


def test_concurrent_access(tmp_path):
    """Multiple threads writing/reading should not crash or corrupt data."""
    db = str(tmp_path / "concurrent.db")
    cache = PersistentCache(ttl_seconds=3600, max_size=50, db_path=db)
    errors = []

    def writer(thread_id):
        try:
            for i in range(20):
                cache.set(f"t{thread_id}_k{i}", f"val{i}")
        except Exception as e:
            errors.append(e)

    def reader(thread_id):
        try:
            for i in range(20):
                cache.get(f"t{thread_id}_k{i}")
        except Exception as e:
            errors.append(e)

    threads = []
    for t in range(5):
        threads.append(threading.Thread(target=writer, args=(t,)))
        threads.append(threading.Thread(target=reader, args=(t,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Concurrent access errors: {errors}"
    # We wrote 5 threads × 20 keys = 100 but max_size is 50
    assert cache.size <= 50


# ── 8. path expansion ────────────────────────────────────────────────


def test_path_expansion():
    """Tilde in db_path should be expanded to home directory."""
    cache = PersistentCache(ttl_seconds=60, max_size=10, db_path="~/test_harvest_cache.db")
    db_path = os.path.expanduser("~/test_harvest_cache.db")

    try:
        assert cache._db_path == db_path
        # Verify DB was actually created at the expanded path
        assert os.path.exists(db_path)

        cache.set("path_test", "works")
        assert cache.get("path_test") == "works"
    finally:
        # Cleanup
        cache.clear()
        if os.path.exists(db_path):
            os.remove(db_path)
        # Also remove WAL/SHM sidecar files
        for suffix in ("-wal", "-shm"):
            sidecar = db_path + suffix
            if os.path.exists(sidecar):
                os.remove(sidecar)


# ── 9. persistence across instances ──────────────────────────────────


def test_persistence_across_instances(tmp_path):
    """Data should survive creating a new cache instance on the same DB."""
    db = str(tmp_path / "persist_test.db")
    c1 = PersistentCache(ttl_seconds=3600, max_size=10, db_path=db)
    c1.set("persistent_key", {"hello": "world"})
    c1.set("another", [1, 2, 3])

    # Create a brand new cache instance on the same file
    c2 = PersistentCache(ttl_seconds=3600, max_size=10, db_path=db)
    assert c2.get("persistent_key") == {"hello": "world"}
    assert c2.get("another") == [1, 2, 3]
    assert c2.size == 2
