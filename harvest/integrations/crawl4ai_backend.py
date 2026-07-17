"""
Harvest ↔ Crawl4AI Backend Integration

Optional scraping backend powered by crawl4ai (73K+ GitHub stars).
Provides Playwright-based crawling with anti-bot detection, deep crawl,
and LLM-ready markdown output.

Architecture:
    Scrapling (default)  →  lightweight, fast, Cloudflare bypass
    Crawl4AI (optional)  →  production-grade, anti-bot, deep crawl, Docker

Usage:
    # Auto-detect
    from harvest.integrations.crawl4ai_backend import Crawl4AIBackend
    backend = Crawl4AIBackend()
    if backend.available:
        result = await backend.scrape("https://example.com")

    # In config.yaml:
    #   scraper:
    #     backend: crawl4ai  # or "scrapling" (default)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Crawl4AIBackend:
    """Crawl4AI-powered scraping backend for Harvest.

    Wraps crawl4ai's AsyncWebCrawler to provide Harvest-compatible
    scraping results. Falls back gracefully if crawl4ai is not installed.
    """

    def __init__(
        self,
        headless: bool = True,
        proxy: Optional[str] = None,
        cache_enabled: bool = True,
        timeout_ms: int = 30000,
    ):
        self.headless = headless
        self.proxy = proxy
        self.cache_enabled = cache_enabled
        self.timeout_ms = timeout_ms
        self._crawler = None
        self._available = False

        try:
            from crawl4ai import BrowserConfig

            self._browser_config = BrowserConfig(
                headless=headless,
                verbose=False,
            )
            if proxy:
                self._browser_config.proxy = proxy
            self._available = True
            logger.info("Crawl4AI backend: available")
        except ImportError:
            logger.debug("Crawl4AI not installed — backend disabled")
        except Exception as e:
            logger.warning(f"Crawl4AI backend init failed: {e}")

    @property
    def available(self) -> bool:
        """Check if crawl4ai is available."""
        return self._available

    async def scrape(
        self,
        url: str,
        css_selector: Optional[str] = None,
        js_code: Optional[str] = None,
        wait_selector: Optional[str] = None,
    ) -> Optional[dict]:
        """Scrape a single URL using crawl4ai.

        Args:
            url: Target URL
            css_selector: CSS selector to extract content from
            js_code: JavaScript to execute before extraction
            wait_selector: Wait for this selector before extracting

        Returns:
            Harvest-compatible result dict with keys:
                url, content, title, markdown, html, metadata
            or None if unavailable
        """
        if not self._available:
            return None

        from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

        cache_mode = CacheMode.ENABLED if self.cache_enabled else CacheMode.BYPASS

        run_config = CrawlerRunConfig(
            cache_mode=cache_mode,
            word_count_threshold=1,
        )

        if css_selector:
            run_config.css_selector = css_selector
        if js_code:
            run_config.js_code = [js_code] if isinstance(js_code, str) else js_code
        if wait_selector:
            run_config.wait_selector = wait_selector

        try:
            async with AsyncWebCrawler(config=self._browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)

                if not result.success:
                    logger.warning(f"Crawl4AI failed for {url}: {result.error_message}")
                    return None

                return {
                    "url": url,
                    "content": result.markdown.fit_markdown or result.markdown.raw_markdown or "",
                    "title": result.metadata.get("title", "") if result.metadata else "",
                    "markdown": result.markdown.raw_markdown or "",
                    "fit_markdown": result.markdown.fit_markdown or "",
                    "html": result.html or "",
                    "metadata": result.metadata or {},
                    "status_code": result.status_code,
                    "backend": "crawl4ai",
                }
        except Exception as e:
            logger.error(f"Crawl4AI scrape failed for {url}: {e}")
            return None

    async def scrape_many(
        self,
        urls: list[str],
        css_selector: Optional[str] = None,
        js_code: Optional[str] = None,
    ) -> list[Optional[dict]]:
        """Scrape multiple URLs concurrently using crawl4ai.

        Args:
            urls: List of target URLs
            css_selector: CSS selector to extract content from
            js_code: JavaScript to execute before extraction

        Returns:
            List of result dicts (None for failed URLs)
        """
        if not self._available:
            return [None] * len(urls)

        from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

        cache_mode = CacheMode.ENABLED if self.cache_enabled else CacheMode.BYPASS

        run_config = CrawlerRunConfig(
            cache_mode=cache_mode,
            word_count_threshold=1,
        )

        if css_selector:
            run_config.css_selector = css_selector
        if js_code:
            run_config.js_code = [js_code] if isinstance(js_code, str) else js_code

        try:
            async with AsyncWebCrawler(config=self._browser_config) as crawler:
                results = await crawler.arun_many(urls=urls, config=run_config)

                output = []
                for result in results:
                    if result.success:
                        output.append(
                            {
                                "url": result.url,
                                "content": result.markdown.fit_markdown or result.markdown.raw_markdown or "",
                                "title": result.metadata.get("title", "") if result.metadata else "",
                                "markdown": result.markdown.raw_markdown or "",
                                "fit_markdown": result.markdown.fit_markdown or "",
                                "html": result.html or "",
                                "metadata": result.metadata or {},
                                "status_code": result.status_code,
                                "backend": "crawl4ai",
                            }
                        )
                    else:
                        logger.warning(f"Crawl4AI failed for {result.url}: {result.error_message}")
                        output.append(None)
                return output
        except Exception as e:
            logger.error(f"Crawl4AI batch scrape failed: {e}")
            return [None] * len(urls)

    async def deep_crawl(
        self,
        start_url: str,
        max_depth: int = 2,
        max_pages: int = 20,
        same_domain: bool = True,
    ) -> list[dict]:
        """Deep crawl using crawl4ai's BFS strategy.

        Args:
            start_url: Starting URL
            max_depth: Maximum crawl depth
            max_pages: Maximum pages to visit
            same_domain: Stay on same domain

        Returns:
            List of scraped results
        """
        if not self._available:
            return []

        from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
        from crawl4ai.deep_crawling import BFSDeepCrawlStrategy

        strategy = BFSDeepCrawlStrategy(
            max_depth=max_depth,
            max_pages=max_pages,
            include_external=not same_domain,
        )

        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            deep_crawl_strategy=strategy,
        )

        try:
            async with AsyncWebCrawler(config=self._browser_config) as crawler:
                results = await crawler.arun_many(
                    urls=[start_url],
                    config=run_config,
                )

                output = []
                for result in results:
                    if result.success:
                        output.append(
                            {
                                "url": result.url,
                                "content": result.markdown.fit_markdown or result.markdown.raw_markdown or "",
                                "title": result.metadata.get("title", "") if result.metadata else "",
                                "markdown": result.markdown.raw_markdown or "",
                                "fit_markdown": result.markdown.fit_markdown or "",
                                "html": result.html or "",
                                "metadata": result.metadata or {},
                                "status_code": result.status_code,
                                "backend": "crawl4ai",
                            }
                        )
                return output
        except Exception as e:
            logger.error(f"Crawl4AI deep crawl failed: {e}")
            return []
