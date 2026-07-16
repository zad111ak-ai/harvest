"""
Crash Recovery — Checkpoint system for long crawls.

Saves crawl state every N URLs so you can resume after crash.

Usage:
    from harvest.recovery import CrawlCheckpoint
    ckpt = CrawlCheckpoint("my-crawl")
    ckpt.save(visited, queue)
    visited, queue = ckpt.load()
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class CrawlCheckpoint:
    """Save and restore crawl state for crash recovery.

    Stores visited URLs, queue, and metadata in JSON files.
    Supports auto-save every N URLs and manual save/load.
    """

    def __init__(
        self,
        crawl_id: str,
        checkpoint_dir: Optional[str] = None,
        auto_save_interval: int = 10,
    ):
        self.crawl_id = crawl_id
        self.dir = Path(checkpoint_dir or "~/.harvest/checkpoints").expanduser()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.auto_save_interval = auto_save_interval
        self._path = self.dir / f"{crawl_id}.json"
        self._save_count = 0

    def save(
        self,
        visited: set,
        queue: list,
        metadata: Optional[dict] = None,
    ) -> Path:
        """Save crawl state to checkpoint file."""
        state = {
            "crawl_id": self.crawl_id,
            "visited": list(visited),
            "queue": queue,
            "visited_count": len(visited),
            "queue_count": len(queue),
            "timestamp": datetime.now().isoformat(),
            "elapsed_s": 0,
            **(metadata or {}),
        }

        self._path.write_text(json.dumps(state, indent=2, default=str))
        return self._path

    def load(self) -> Optional[dict]:
        """Load crawl state from checkpoint.

        Returns:
            dict with 'visited' (set), 'queue' (list), and metadata,
            or None if no checkpoint exists.
        """
        if not self._path.exists():
            return None

        try:
            state = json.loads(self._path.read_text())
            state["visited"] = set(state.get("visited", []))
            return state
        except (json.JSONDecodeError, KeyError):
            return None

    def exists(self) -> bool:
        """Check if checkpoint exists."""
        return self._path.exists()

    def delete(self) -> None:
        """Delete checkpoint file."""
        if self._path.exists():
            self._path.unlink()

    def maybe_save(self, visited: set, queue: list, metadata: Optional[dict] = None) -> bool:
        """Auto-save every N URLs. Returns True if saved."""
        self._save_count += 1
        if self._save_count % self.auto_save_interval == 0:
            self.save(visited, queue, metadata)
            return True
        return False

    def get_info(self) -> Optional[dict]:
        """Get checkpoint info without fully loading."""
        if not self._path.exists():
            return None

        try:
            state = json.loads(self._path.read_text())
            return {
                "crawl_id": state.get("crawl_id"),
                "visited_count": state.get("visited_count", 0),
                "queue_count": state.get("queue_count", 0),
                "timestamp": state.get("timestamp"),
            }
        except (json.JSONDecodeError, KeyError):
            return None

    @classmethod
    def list_checkpoints(cls, checkpoint_dir: Optional[str] = None) -> list[dict]:
        """List all available checkpoints."""
        d = Path(checkpoint_dir or "~/.harvest/checkpoints").expanduser()
        if not d.exists():
            return []

        results = []
        for f in sorted(d.glob("*.json")):
            try:
                state = json.loads(f.read_text())
                results.append(
                    {
                        "crawl_id": state.get("crawl_id"),
                        "visited_count": state.get("visited_count", 0),
                        "queue_count": state.get("queue_count", 0),
                        "timestamp": state.get("timestamp"),
                        "file": str(f),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue

        return results
