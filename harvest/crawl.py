"""
Crawl — Sitemap discovery and bulk page extraction.

Like Scrapy's crawl spider, but one command. Finds all internal links
and extracts content from each page.

Usage:
    harvest crawl https://site.com --max-pages 50
    harvest crawl https://site.com --sitemap-only
    harvest crawl https://site.com --same-domain --delay 1.0
"""

import asyncio
import re
import time
from typing import Any, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime

from .core import Scraper
from .dashboard import Dashboard, NullDashboard


class SiteCrawler:
    """Discover and extract pages from a website.

    Features:
    - Sitemap.xml discovery (auto-detect + robots.txt)
    - Same-domain link crawling with depth limit
    - Concurrent fetch with rate limiting
    - Deduplication + visited tracking
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def __init__(
        self,
        proxy: Optional[str] = None,
        headless: bool = True,
        max_concurrent: int = 5,
        delay: float = 0.5,
    ):
        self.scraper = Scraper(proxy=proxy, headless=headless)
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.visited: set[str] = set()
        self.last_fetch_time = 0.0

    async def crawl(
        self,
        start_url: str,
        max_pages: int = 50,
        same_domain: bool = True,
        sitemap_only: bool = False,
        include_pattern: Optional[str] = None,
        exclude_pattern: Optional[str] = None,
    ) -> dict:
        """Crawl a website starting from a URL.

        Args:
            start_url: Entry point URL
            max_pages: Max pages to scrape (0 = unlimited)
            same_domain: Stay on the same domain
            sitemap_only: Only fetch pages from sitemap
            include_pattern: Only crawl URLs matching this regex
            exclude_pattern: Skip URLs matching this regex

        Returns:
            dict with pages, sitemap_urls, stats
        """
        base_domain = urlparse(start_url).netloc
        include_re = re.compile(include_pattern) if include_pattern else None
        exclude_re = re.compile(exclude_pattern) if exclude_pattern else None

        pages: list[dict[str, Any]] = []
        dash = (
            Dashboard(total=max_pages, description=f"Crawling {urlparse(start_url).netloc}")
            if max_pages > 0
            else NullDashboard()
        )
        dash.start()
        sitemap_urls = []

        # Step 1: Discover sitemap
        try:
            sitemap_urls = await self._discover_sitemap(start_url)
        except Exception:
            pass

        # Step 2: Build URL queue
        to_visit: list[str] = []

        if sitemap_urls:
            for sm_url in sitemap_urls:
                to_visit.append(sm_url)

        if not sitemap_only and start_url not in to_visit:
            to_visit.append(start_url)

        # Step 3: Crawl
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def fetch_page(url: str) -> Optional[dict]:
            if url in self.visited:
                return None
            self.visited.add(url)

            # Rate limiting
            elapsed = time.time() - self.last_fetch_time
            if elapsed < self.delay:
                await asyncio.sleep(self.delay - elapsed)

            self.last_fetch_time = time.time()

            try:
                async with semaphore:
                    result = await self.scraper.scrape(url)
                    self.last_fetch_time = time.time()

                # Discover more links if we haven't hit max
                if len(pages) < max_pages:
                    new_links = self._find_internal_links(result.get("content", ""), start_url, base_domain)
                    for link in new_links:
                        if link not in self.visited and link not in to_visit and link != url:
                            if exclude_re and exclude_re.search(link):
                                continue
                            if include_re and not include_re.search(link):
                                continue
                            to_visit.append(link)

                dash.update(url, success=True)
                return result
            except Exception as e:
                dash.update(url, success=False)
                return {
                    "url": url,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }

        # Process queue
        i = 0
        while to_visit and len(pages) < max_pages:
            url = to_visit.pop(0)
            page = await fetch_page(url)
            if page:
                pages.append(page)
            i += 1
            if i > max_pages * 3:  # Safety: skip queue emptier
                break

        dash.stop()
        return {
            "start_url": start_url,
            "total_pages": len(pages),
            "total_discovered": len(self.visited),
            "sitemap_urls": sitemap_urls,
            "pages": pages,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _discover_sitemap(self, url: str) -> list[str]:
        """Discover sitemap URLs from robots.txt and common locations."""
        base = self._base_url(url)
        discovered = []

        # Try robots.txt
        try:
            robots_url = urljoin(base, "/robots.txt")
            robots_page = await self.scraper.scrape(robots_url)
            content = robots_page.get("content", "")
            for match in re.finditer(r"Sitemap:\s*(https?://\S+)", content, re.IGNORECASE):
                discovered.append(match.group(1))
        except Exception:
            pass

        # Try common sitemap locations
        common = [
            "/sitemap.xml",
            "/sitemap_index.xml",
            "/sitemap/",
            "/sitemap/sitemap.xml",
            "/sitemap1.xml",
        ]
        for path in common:
            try:
                sm_url = urljoin(base, path)
                sm_page = await self.scraper.scrape(sm_url)
                content = sm_page.get("content", "")
                # Sitemap index: contains <loc> children
                locs = re.findall(r"<loc>(.*?)</loc>", content, re.IGNORECASE)
                if locs:
                    # Might be a sitemap index pointing to sub-sitemaps
                    if len(locs) > 50:
                        # This is probably a sub-sitemap's URLs, return raw
                        discovered.extend(locs)
                    else:
                        discovered.append(sm_url)
            except Exception:
                pass

        return list(set(discovered))

    def _find_internal_links(self, html: str, base_url: str, domain: str) -> list[str]:
        """Extract internal links from HTML content."""
        links = set()
        for match in re.finditer(r'href=["\'](https?://[^"\']+|/[^"\']+)["\']', html):
            link = match.group(1)
            if link.startswith("/"):
                link = urljoin(base_url, link)
            try:
                parsed = urlparse(link)
                if (
                    parsed.netloc == domain
                    or parsed.netloc == domain.replace("www.", "")
                    or parsed.netloc == f"www.{domain}"
                ):
                    # Clean URL
                    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
                    if clean and "#" not in clean:
                        links.add(clean)
            except Exception:
                pass
        return list(links)

    def _base_url(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
