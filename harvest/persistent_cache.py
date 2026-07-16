"""PersistentCache — SQLite-backed disk-persistent TTL cache for Harvest.

Same interface as ResponseCache (get/set/invalidate/clear + size property)
plus a stats() method, but persists to disk via SQLite in WAL mode.

Usage:
    cache = PersistentCache(ttl_seconds=300, max_size=5000)
    result = cache.get(url)
    if not result:
        result = await scrape(url)
        cache.set(url, result)
"""

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional


class PersistentCache:
    """SQLite-backed cache with TTL, max-size eviction, and WAL mode."""

    _DEFAULT_DB_PATH = "~/.harvest/cache.db"

    def __init__(
        self,
        ttl_seconds: int = 300,
        max_size: int = 1000,
        db_path: Optional[str] = None,
    ):
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._db_path = str(Path(db_path or self._DEFAULT_DB_PATH).expanduser())
        self._lock = threading.Lock()
        self._init_db()

    # ── database helpers ──────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        """Open a new connection (each thread should use its own)."""
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self):
        """Create table and indexes if they don't exist."""
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key       TEXT PRIMARY KEY,
                    value     TEXT NOT NULL,
                    created   REAL NOT NULL
                )
            """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON cache(created)")
            conn.commit()
        finally:
            conn.close()

    # ── public interface ──────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """Return cached value if not expired, else None."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT value, created FROM cache WHERE key = ?", (key,)).fetchone()
                if row is None:
                    return None
                value, created = row
                if time.time() - created > self._ttl:
                    conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                    conn.commit()
                    return None
                return json.loads(value)
            finally:
                conn.close()

    def set(self, key: str, value: Any):
        """Cache *value* under *key*. Evicts when over max_size."""
        serialized = json.dumps(value)
        with self._lock:
            conn = self._connect()
            try:
                # Evict expired first, then oldest if still over limit
                self._evict_expired(conn)
                count = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
                if count >= self._max_size:
                    self._evict_oldest(conn, count)
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value, created) VALUES (?, ?, ?)",
                    (key, serialized, time.time()),
                )
                conn.commit()
            finally:
                conn.close()

    def invalidate(self, key: str):
        """Remove a specific entry."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
            finally:
                conn.close()

    def clear(self):
        """Remove all entries."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM cache")
                conn.commit()
            finally:
                conn.close()

    @property
    def size(self) -> int:
        """Number of non-expired entries."""
        with self._lock:
            conn = self._connect()
            try:
                self._evict_expired(conn)
                conn.commit()
                return conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            finally:
                conn.close()

    def stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            conn = self._connect()
            try:
                self._evict_expired(conn)
                conn.commit()
                total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
                pass
                oldest = conn.execute("SELECT MIN(created) FROM cache").fetchone()[0]
                newest = conn.execute("SELECT MAX(created) FROM cache").fetchone()[0]
                return {
                    "total_entries": total,
                    "max_size": self._max_size,
                    "ttl_seconds": self._ttl,
                    "db_path": self._db_path,
                    "oldest_entry_age": (time.time() - oldest if oldest else None),
                    "newest_entry_age": (time.time() - newest if newest else None),
                }
            finally:
                conn.close()

    # ── internal helpers ──────────────────────────────────────────────

    def _evict_expired(self, conn: sqlite3.Connection):
        """Remove all expired entries."""
        cutoff = time.time() - self._ttl
        conn.execute("DELETE FROM cache WHERE created < ?", (cutoff,))

    def _evict_oldest(self, conn: sqlite3.Connection, current_count: int):
        """Remove oldest entries until we're below max_size."""
        to_remove = current_count - self._max_size + 1
        if to_remove > 0:
            conn.execute(
                """
                DELETE FROM cache WHERE key IN (
                    SELECT key FROM cache ORDER BY created ASC LIMIT ?
                )
                """,
                (to_remove,),
            )
