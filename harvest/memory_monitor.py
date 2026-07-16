"""
Memory Monitor — Track memory usage during scraping operations.

Helps detect memory leaks, optimize batch sizes, and prevent OOM.

Usage:
    from harvest.memory_monitor import MemoryMonitor
    monitor = MemoryMonitor()
    monitor.start()
    # ... do scraping ...
    print(monitor.report())
"""

import os
import time
from typing import Optional

try:
    import psutil

    HAVE_PSUTIL = True
except ImportError:
    HAVE_PSUTIL = False


class MemoryMonitor:
    """Monitor memory usage during scraping.

    Tracks start/current/peak memory and provides recommendations.
    """

    def __init__(self, warn_threshold_mb: float = 500, critical_threshold_mb: float = 1024):
        self.warn_threshold = warn_threshold_mb
        self.critical_threshold = critical_threshold_mb
        self.start_memory_mb: float = 0
        self.peak_memory_mb: float = 0
        self.start_time: Optional[float] = None
        self._snapshots: list[dict] = []
        self._process = None

        if HAVE_PSUTIL:
            self._process = psutil.Process(os.getpid())

    def start(self) -> None:
        """Start monitoring."""
        self.start_time = time.monotonic()
        if self._process:
            self.start_memory_mb = self._get_memory_mb()
            self.peak_memory_mb = self.start_memory_mb

    def _get_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        if self._process:
            return self._process.memory_info().rss / 1024 / 1024
        return 0

    def snapshot(self, label: str = "") -> dict:
        """Take a memory snapshot."""
        current = self._get_memory_mb()
        self.peak_memory_mb = max(self.peak_memory_mb, current)

        elapsed = time.monotonic() - self.start_time if self.start_time else 0

        snap = {
            "label": label,
            "current_mb": round(current, 1),
            "peak_mb": round(self.peak_memory_mb, 1),
            "start_mb": round(self.start_memory_mb, 1),
            "increase_mb": round(current - self.start_memory_mb, 1),
            "elapsed_s": round(elapsed, 1),
        }
        self._snapshots.append(snap)
        return snap

    def get_status(self) -> str:
        """Get emoji status based on memory usage."""
        current = self._get_memory_mb()
        if current > self.critical_threshold:
            return "🔴 CRITICAL"
        elif current > self.warn_threshold:
            return "🟡 WARNING"
        return "🟢 OK"

    def report(self) -> str:
        """Generate a human-readable memory report."""
        if not HAVE_PSUTIL:
            return "⚠️  psutil not installed. Run: pip install psutil"

        current = self._get_memory_mb()
        elapsed = time.monotonic() - self.start_time if self.start_time else 0

        report = f"""
📊 Memory Report
{"━" * 50}
Start:    {self.start_memory_mb:.1f} MB
Current:  {current:.1f} MB
Peak:     {self.peak_memory_mb:.1f} MB
Increase: {current - self.start_memory_mb:.1f} MB
Status:   {self.get_status()}
Elapsed:  {elapsed:.1f}s

💡 Recommendations:
"""
        increase = current - self.start_memory_mb

        if increase > 200:
            report += "  ⚠️  High memory growth — check for leaks\n"
        if increase > 100:
            report += "  💡 Consider smaller batch sizes\n"
        if self.peak_memory_mb > 800:
            report += "  🔥 Peak > 800MB — enable browser pooling\n"
        if increase < 10:
            report += "  ✅ Memory usage looks healthy\n"

        if self._snapshots and len(self._snapshots) > 2:
            # Check for trend
            recent = self._snapshots[-3:]
            increases = [s["increase_mb"] for s in recent]
            if all(increases[i] < increases[i + 1] for i in range(len(increases) - 1)):
                report += "  📈 Memory trending upward — possible leak\n"

        return report

    def get_stats(self) -> dict:
        """Get stats dict for dashboard integration."""
        current = self._get_memory_mb()
        return {
            "current_mb": round(current, 1),
            "peak_mb": round(self.peak_memory_mb, 1),
            "start_mb": round(self.start_memory_mb, 1),
            "increase_mb": round(current - self.start_memory_mb, 1),
            "status": self.get_status(),
            "snapshots": len(self._snapshots),
        }
