"""
WebSocket Streaming — Real-time stats via WebSocket.

Streams live metrics (cache hits, active scrapes, memory) to web dashboard.

Usage:
    from harvest.streaming import StatsStreamer
    streamer = StatsStreamer()
    streamer.start()
"""

import asyncio
import time
from datetime import datetime
from typing import Optional, Any


class StatsCollector:
    """Collect stats from various Harvest components."""

    def __init__(self):
        self.cache_hits = 0
        self.cache_misses = 0
        self.active_scrapes = 0
        self.total_scrapes = 0
        self.failed_scrapes = 0
        self.start_time = time.monotonic()
        self._subscribers: list = []

    def record_cache_hit(self):
        self.cache_hits += 1

    def record_cache_miss(self):
        self.cache_misses += 1

    def scrape_started(self):
        self.active_scrapes += 1
        self.total_scrapes += 1

    def scrape_finished(self, success: bool = True):
        self.active_scrapes = max(0, self.active_scrapes - 1)
        if not success:
            self.failed_scrapes += 1

    def get_stats(self) -> dict:
        total = self.cache_hits + self.cache_misses
        elapsed = time.monotonic() - self.start_time
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_ratio": f"{self.cache_hits / total * 100:.1f}%" if total > 0 else "N/A",
            "active_scrapes": self.active_scrapes,
            "total_scrapes": self.total_scrapes,
            "failed_scrapes": self.failed_scrapes,
            "success_rate": f"{(self.total_scrapes - self.failed_scrapes) / self.total_scrapes * 100:.1f}%"
            if self.total_scrapes > 0
            else "N/A",
            "uptime_s": round(elapsed, 1),
            "timestamp": datetime.now().isoformat(),
        }


class StatsStreamer:
    """Stream stats to connected WebSocket clients.

    Usage:
        streamer = StatsStreamer()
        # Register as FastAPI route
        # @app.websocket("/ws/stats")
        # async def ws(websocket):
        #     await streamer.serve(websocket)
    """

    def __init__(self, interval: float = 2.0):
        self.collector = StatsCollector()
        self.interval = interval
        self._clients: list = []

    async def serve(self, websocket: Any) -> None:
        """Serve stats to a WebSocket client."""
        await websocket.accept()
        self._clients.append(websocket)

        try:
            while True:
                stats = self.collector.get_stats()
                await websocket.send_json(stats)
                await asyncio.sleep(self.interval)
        except Exception:
            pass
        finally:
            if websocket in self._clients:
                self._clients.remove(websocket)

    async def broadcast(self) -> None:
        """Broadcast stats to all connected clients."""
        if not self._clients:
            return

        stats = self.collector.get_stats()
        dead = []

        for ws in self._clients:
            try:
                await ws.send_json(stats)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._clients.remove(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)


# Global instance
_collector: Optional[StatsCollector] = None
_streamer: Optional[StatsStreamer] = None


def get_collector() -> StatsCollector:
    """Get the global stats collector."""
    global _collector
    if _collector is None:
        _collector = StatsCollector()
    return _collector


def get_streamer() -> StatsStreamer:
    """Get the global stats streamer."""
    global _streamer
    if _streamer is None:
        _streamer = StatsStreamer()
        _streamer.collector = get_collector()
    return _streamer
