"""Failure tracker — log failed URLs for retry and analysis."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class FailureTracker:
    """Track and log failed scraping attempts."""

    def __init__(self, log_file: Optional[str] = None):
        self.log_file = Path(log_file) if log_file else Path.home() / ".harvest" / "failed_urls.jsonl"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def record_failure(self, url: str, error: str, context: str = "") -> None:
        """Record a failed URL for later retry."""
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "url": url,
            "error": error[:500],
            "context": context,
        }
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_failed_urls(self, limit: int = 100) -> list[dict]:
        """Read failed URLs from log."""
        if not self.log_file.exists():
            return []
        results = []
        with open(self.log_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(results) >= limit:
                    break
        return results

    def clear(self) -> None:
        """Clear the failure log."""
        if self.log_file.exists():
            self.log_file.unlink()


# Global instance
failure_tracker = FailureTracker()
