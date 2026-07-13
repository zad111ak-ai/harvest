"""Structured logging for Harvest — JSON format for production, readable for dev."""

import json
import sys
import time
from datetime import datetime
from typing import Any


class StructuredLogger:
    """JSON structured logger for production observability."""

    def __init__(self, name: str = "harvest", json_format: bool = False):
        self.name = name
        self.json_format = json_format
        self._start_time = time.monotonic()

    def _emit(self, level: str, event: str, **kwargs: Any) -> None:
        elapsed = time.monotonic() - self._start_time
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "logger": self.name,
            "event": event,
            "elapsed_s": round(elapsed, 2),
            **kwargs,
        }
        if self.json_format:
            print(json.dumps(entry, ensure_ascii=False), file=sys.stderr)
        else:
            extras = " ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
            suffix = f" {extras}" if extras else ""
            print(f"[{level}] {event}{suffix}", file=sys.stderr)

    def info(self, event: str, **kwargs: Any) -> None:
        self._emit("INFO", event, **kwargs)

    def warn(self, event: str, **kwargs: Any) -> None:
        self._emit("WARN", event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._emit("ERROR", event, **kwargs)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._emit("DEBUG", event, **kwargs)


# Global logger instance
logger = StructuredLogger()
