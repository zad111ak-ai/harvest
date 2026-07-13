"""Dashboard — Rich terminal progress display for Harvest.

Shows live progress during crawl/batch operations:
- Progress bar with percentage
- Success/failure counts
- Pages/sec rate
- Active URLs being processed
"""

import time
from typing import Any

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        Progress,
        SpinnerColumn,
        BarColumn,
        TextColumn,
        TimeElapsedColumn,
        MofNCompleteColumn,
    )
    from rich.table import Table
    from rich.text import Text

    HAVE_RICH = True
except ImportError:
    HAVE_RICH = False


class Dashboard:
    """Live progress dashboard for long-running operations."""

    def __init__(self, total: int = 0, description: str = "Scraping"):
        self.total = total
        self.description = description
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self.start_time = time.monotonic()
        self.current_url = ""
        self._progress: Any = None
        self._live: Any = None
        self._task_id = None

        if HAVE_RICH:
            self.console = Console()
            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40),
                MofNCompleteColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console,
            )
            self._task_id = self._progress.add_task(description, total=total)

    def update(self, url: str = "", success: bool = True, skipped: bool = False) -> None:
        """Update progress after processing a URL."""
        if skipped:
            self.skipped += 1
        elif success:
            self.success += 1
        else:
            self.failed += 1

        self.current_url = url[:80] if url else ""

        if HAVE_RICH and self._progress and self._task_id is not None:
            self._progress.advance(self._task_id)

    def start(self) -> None:
        """Start live display."""
        if HAVE_RICH and self._progress:
            self._live = Live(self._render(), console=self.console, refresh_per_second=4)
            self._live.start()

    def stop(self) -> None:
        """Stop live display and print summary."""
        if HAVE_RICH and self._live:
            self._live.stop()
        self._print_summary()

    def _render(self) -> Any:
        """Render current state as Rich renderable."""
        if not HAVE_RICH:
            return ""

        elapsed = time.monotonic() - self.start_time
        rate = (self.success + self.failed) / elapsed if elapsed > 0 else 0

        table = Table.grid(padding=1)
        table.add_row(self._progress)
        table.add_row(
            Text(
                f"  ✅ {self.success}  ❌ {self.failed}  ⏭️ {self.skipped}  ⚡ {rate:.1f} pages/s",
                style="dim",
            ),
        )
        if self.current_url:
            table.add_row(Text(f"  → {self.current_url}", style="dim cyan"))

        return Panel(table, title="[bold]Harvest[/bold]", border_style="blue")

    def _print_summary(self) -> None:
        """Print final summary."""
        elapsed = time.monotonic() - self.start_time
        total = self.success + self.failed + self.skipped
        rate = total / elapsed if elapsed > 0 else 0

        if HAVE_RICH:
            self.console.print()
            self.console.print(
                Panel(
                    f"[green]✅ {self.success}[/green] success  •  "
                    f"[red]❌ {self.failed}[/red] failed  •  "
                    f"[yellow]⏭️ {self.skipped}[/yellow] skipped\n"
                    f"⏱️ {elapsed:.1f}s total  •  ⚡ {rate:.1f} pages/s",
                    title="[bold]Done[/bold]",
                    border_style="green",
                )
            )
        else:
            print(f"\n✅ {self.success} success | ❌ {self.failed} failed | ⏭️ {self.skipped} skipped")
            print(f"⏱️ {elapsed:.1f}s | ⚡ {rate:.1f} pages/s")


class NullDashboard:
    """No-op dashboard for when Rich is unavailable or progress isn't needed."""

    def update(self, url: str = "", success: bool = True, skipped: bool = False) -> None:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
