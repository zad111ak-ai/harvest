"""Batch — Bulk URL processing with concurrency, rate limiting, and retries.

Process hundreds of URLs with controlled parallelism, delay between requests,
and optional rate limiting. Results can be exported or piped to other commands.

Usage:
    harvest batch urls.txt
    harvest batch urls.txt --concurrency 10 --delay 1.0
    harvest batch urls.txt --rate-limit 30 --export results.json
    harvest batch --sitemap https://example.com/sitemap.xml --concurrency 5
"""

import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from .core import Scraper
from .dashboard import Dashboard
from .export import Exporter
from .extract import SchemaExtractor


@dataclass
class BatchResult:
    """Result of a batch operation."""

    total: int = 0
    success: int = 0
    failed: int = 0
    results: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    duration: float = 0.0

    def __iter__(self):
        return iter(self.results)

    def __len__(self):
        return len(self.results)

    def __getitem__(self, idx):
        return self.results[idx]


class BatchProcessor:
    """Process multiple URLs concurrently with rate limiting and retries.

    Args:
        concurrency: Max parallel requests (default 5).
        delay: Seconds between batches (default 0.5).
        rate_limit: Max requests per minute (0 = unlimited).
        retries: Retry attempts per URL (default 3).
        proxy: Optional HTTP proxy.
        headless: Browser headless mode (default True).
    """

    def __init__(
        self,
        concurrency: int = 5,
        delay: float = 0.5,
        rate_limit: int = 0,
        retries: int = 3,
        proxy: Optional[str] = None,
        headless: bool = True,
    ):
        self.concurrency = concurrency
        self.delay = delay
        self.rate_limit = rate_limit
        self.retries = retries
        self.proxy = proxy
        self.headless = headless

    async def process_urls(
        self,
        urls: list[str],
        selector: Optional[str] = None,
        extract_schema: Optional[dict] = None,
    ) -> BatchResult:
        """Process a list of URLs concurrently.

        Args:
            urls: List of URLs to process.
            selector: Optional CSS selector for content extraction.
            extract_schema: Optional schema for structured extraction.

        Returns:
            BatchResult with stats and individual results.
        """
        scraper = Scraper(proxy=self.proxy, headless=self.headless)
        sem = asyncio.Semaphore(self.concurrency)
        result = BatchResult(total=len(urls))
        start = time.time()

        rate_limit_sem: Optional[asyncio.Semaphore] = None
        if self.rate_limit > 0:
            rate_limit_sem = asyncio.Semaphore(self.rate_limit)

        async def process_one(url: str) -> dict:
            async with sem:
                if rate_limit_sem:
                    async with rate_limit_sem:
                        pass
                    await asyncio.sleep(60.0 / self.rate_limit)

                for attempt in range(self.retries):
                    try:
                        if extract_schema:
                            ex = SchemaExtractor(proxy=self.proxy, headless=self.headless)
                            out = await ex.extract(url, extract_schema)
                        else:
                            out = await scraper.scrape(url, selector=selector)
                        return {
                            "url": url,
                            "status": "ok",
                            "data": out,
                            "attempts": attempt + 1,
                        }
                    except Exception as e:
                        if attempt < self.retries - 1:
                            await asyncio.sleep(self.delay * (attempt + 1))
                        else:
                            return {
                                "url": url,
                                "status": "error",
                                "error": str(e),
                                "attempts": attempt + 1,
                            }

        dash = Dashboard(total=len(urls), description="Batch processing")
        dash.start()
        tasks = [process_one(url) for url in urls]
        outputs = await asyncio.gather(*tasks)

        for out in outputs:
            if out["status"] == "ok":
                dash.update(out["url"], success=True)
                result.success += 1
                result.results.append(out)
            else:
                dash.update(out["url"], success=False)
                result.failed += 1
                result.errors.append(out)

        dash.stop()
        result.duration = time.time() - start
        return result

    async def process_file(
        self,
        file_path: str,
        selector: Optional[str] = None,
        extract_schema: Optional[dict] = None,
    ) -> BatchResult:
        """Read URLs from a file (one per line) and process them.

        Lines starting with # or empty lines are skipped.
        """
        path = Path(file_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"URL file not found: {file_path}")

        raw = path.read_text(encoding="utf-8")
        urls = [line.strip() for line in raw.splitlines() if line.strip() and not line.strip().startswith("#")]

        if not urls:
            return BatchResult()

        return await self.process_urls(urls, selector=selector, extract_schema=extract_schema)

    async def process_sitemap(
        self,
        sitemap_url: str,
        selector: Optional[str] = None,
        extract_schema: Optional[dict] = None,
    ) -> BatchResult:
        """Fetch sitemap, extract URLs, and process them."""
        scraper = Scraper(proxy=self.proxy, headless=self.headless)
        sitemap_result = await scraper.scrape(sitemap_url, extraction="text")

        urls = self._parse_sitemap(sitemap_result.get("content", ""))
        if not urls:
            return BatchResult()

        return await self.process_urls(urls, selector=selector, extract_schema=extract_schema)

    @staticmethod
    def _parse_sitemap(content: str) -> list[str]:
        """Extract URLs from sitemap XML text."""
        import re

        urls = re.findall(r"<loc>(.*?)</loc>", content)
        return [u.strip() for u in urls]

    def export_results(
        self,
        result: BatchResult,
        output: str,
        fmt: str = "json",
    ) -> str:
        """Export batch results to a file.

        Returns the file path.
        """
        path = Path(output)

        if fmt == "json":
            data = asdict(result)
            data["results"] = data.pop("results")
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        elif fmt == "csv":
            rows = [r.get("data", {}) for r in result.results if r.get("data")]
            csv = Exporter.to_csv(rows)
            path.write_text(csv, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

        return str(path.resolve())

    @staticmethod
    def print_summary(result: BatchResult):
        """Print a human-readable summary of batch results."""
        rate = result.success / result.duration if result.duration > 0 else 0
        print(f"\n🌾 Batch complete: {result.total} URLs in {result.duration:.1f}s ({rate:.1f}/s)")
        print(f"   ✅ {result.success} success | ❌ {result.failed} failed")
        if result.duration > 0:
            print(f"   ⏱ {result.duration:.1f}s total")
        if result.errors:
            print(f"\n   Errors ({len(result.errors)}):")
            for e in result.errors[:5]:
                print(f"     ✗ {e['url']}: {e['error'][:80]}")
            if len(result.errors) > 5:
                print(f"     ... and {len(result.errors) - 5} more")
