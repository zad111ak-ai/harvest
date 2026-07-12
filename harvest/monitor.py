"""
Monitor — Track changes in web pages over time.
Detect diffs in pricing, content, layouts.
"""
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

from .core import Scraper


class ChangeWatcher:
    """Monitor web pages for content changes.

    Stores snapshots locally and produces diffs.
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or "~/.harvest").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.scraper = Scraper()

    def _snapshot_path(self, url_hash: str) -> Path:
        return self.data_dir / f"{url_hash}.json"

    def _url_hash(self, url: str) -> str:
        import hashlib

        return hashlib.md5(url.encode()).hexdigest()[:16]

    async def check(self, url: str, selector: Optional[str] = None) -> dict:
        """Scrape and compare with previous snapshot.

        Returns:
            dict with: url, changed (bool), diff_text, snapshot, previous_snapshot
        """
        result = await self.scraper.scrape(url, selector)
        content = result["content"]
        url_id = self._url_hash(url)
        snap_path = self._snapshot_path(url_id)

        previous = None
        if snap_path.exists():
            with open(snap_path) as f:
                previous = json.load(f)

        changed = False
        diff_text = ""

        if previous:
            prev_content = previous.get("content", "")
            if prev_content != content:
                changed = True
                # Simple line-based diff
                prev_lines = prev_content.split("\n")
                curr_lines = content.split("\n")
                added = [l for l in curr_lines if l not in prev_lines]
                removed = [l for l in prev_lines if l not in curr_lines]
                if added:
                    diff_text += f"[+] {len(added)} lines added\n"
                    diff_text += "\n".join(added[:10])
                    if len(added) > 10:
                        diff_text += f"\n... and {len(added) - 10} more"
                if removed:
                    diff_text += f"\n[-] {len(removed)} lines removed\n"
                    diff_text += "\n".join(removed[:5])
                    if len(removed) > 5:
                        diff_text += f"\n... and {len(removed) - 5} more"
            else:
                diff_text = "No changes detected"
        else:
            diff_text = "First snapshot — no previous data"

        # Save current snapshot
        snapshot = {
            "url": url,
            "content": content,
            "timestamp": result["timestamp"],
            "title": result.get("title", ""),
        }
        with open(snap_path, "w") as f:
            json.dump(snapshot, f, indent=2)

        return {
            "url": url,
            "changed": changed,
            "diff_text": diff_text,
            "title": result.get("title", ""),
            "timestamp": result["timestamp"],
            "previous_snapshot_time": previous.get("timestamp") if previous else None,
        }

    async def history(self, url: str) -> list[dict]:
        """Get all historical snapshots for a URL."""
        # Only stores latest snapshot; for proper history, we'd need a DB
        url_id = self._url_hash(url)
        snap_path = self._snapshot_path(url_id)
        if snap_path.exists():
            with open(snap_path) as f:
                return [json.load(f)]
        return []
