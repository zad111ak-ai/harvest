"""Live integration tests — scrape real websites to verify Harvest works end-to-end.

These tests hit actual websites. They're designed to be:
- Economical: use HTTP-only scraping where possible, browser only when needed
- Reliable: use stable test sites that won't go down
- Fast: skip heavy browser rendering unless testing JS/CF bypass
"""

import pytest

from harvest.core import Scraper
from harvest.extract import SchemaExtractor
from harvest.crawl import SiteCrawler
from harvest.contacts import ContactCollector


# Stable test sites that are always available
TEST_SITES = {
    "books": "https://books.toscrape.com/",
    "quotes": "https://quotes.toscrape.com/",
    "example": "https://example.com/",
    "httpbin": "https://httpbin.org/html",
    "github": "https://github.com/zad111ak-ai/harvest",
}


class TestLiveScrape:
    """Test basic scraping against real sites."""

    @pytest.mark.asyncio
    async def test_books_toscrape(self):
        """Scrape books.toscrape.com — classic test site."""
        async with Scraper(use_stealth=False, use_captcha_solver=False, use_rotator=False) as s:
            result = await s.scrape(TEST_SITES["books"])
            assert result["content"], "No content from books.toscrape.com"
            assert "Books to Scrape" in result.get("title", "") or len(result["content"]) > 100

    @pytest.mark.asyncio
    async def test_example_com(self):
        """Scrape example.com — simplest possible site."""
        async with Scraper(use_stealth=False, use_captcha_solver=False, use_rotator=False) as s:
            result = await s.scrape(TEST_SITES["example"])
            assert result["content"], "No content from example.com"
            assert "Example Domain" in result.get("title", "") or "example" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_httpbin_html(self):
        """Scrape httpbin.org/html — returns simple HTML."""
        async with Scraper(use_stealth=False, use_captcha_solver=False, use_rotator=False) as s:
            result = await s.scrape(TEST_SITES["httpbin"])
            assert result["content"], "No content from httpbin.org/html"
            assert "Herman Melville" in result["content"] or len(result["content"]) > 50

    @pytest.mark.asyncio
    async def test_github_repo_page(self):
        """Scrape a GitHub repo page — real-world structured data."""
        async with Scraper(use_stealth=False, use_captcha_solver=False, use_rotator=False) as s:
            result = await s.scrape(TEST_SITES["github"])
            assert result["content"], "No content from GitHub"
            assert "harvest" in result["content"].lower() or "zad111ak" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_scrape_many(self):
        """Scrape multiple URLs concurrently."""
        urls = [TEST_SITES["example"], TEST_SITES["httpbin"]]
        async with Scraper(use_stealth=False, use_captcha_solver=False, use_rotator=False) as s:
            results = await s.scrape_many(urls)
            assert len(results) == 2
            assert all(r.get("content") for r in results if isinstance(r, dict))


class TestLiveSchemaExtract:
    """Test CSS schema extraction against real sites."""

    @pytest.mark.asyncio
    async def test_books_schema_extract(self):
        """Extract book titles and prices from books.toscrape.com."""
        schema = {
            "_type": "list",
            "_selector": ".product_pod",
            "title": "h3 a",
            "price": ".price_color",
        }
        extractor = SchemaExtractor()
        result = await extractor.extract(TEST_SITES["books"], schema)
        assert result["extracted"], "No data extracted"
        assert len(result["extracted"]) > 0, "Empty extraction"

    @pytest.mark.asyncio
    async def test_quotes_schema_extract(self):
        """Extract quotes from quotes.toscrape.com."""
        schema = {
            "_type": "list",
            "_selector": ".quote",
            "text": ".text",
            "author": ".author",
        }
        extractor = SchemaExtractor()
        result = await extractor.extract(TEST_SITES["quotes"], schema)
        assert result["extracted"], "No data extracted from quotes"
        assert len(result["extracted"]) > 0


class TestLiveCrawl:
    """Test site crawling against real sites."""

    @pytest.mark.asyncio
    async def test_crawl_books_toscrape(self):
        """Crawl books.toscrape.com — should find multiple pages."""
        crawler = SiteCrawler()
        result = await crawler.crawl(TEST_SITES["books"], max_pages=3)
        assert result["pages_crawled"] > 0, "No pages crawled"
        assert result["urls_found"] > 0, "No URLs found"

    @pytest.mark.asyncio
    async def test_crawl_quotes(self):
        """Crawl quotes.toscrape.com — limited depth."""
        crawler = SiteCrawler()
        result = await crawler.crawl(TEST_SITES["quotes"], max_pages=2)
        assert result["pages_crawled"] > 0, "No pages crawled"


class TestLiveContactFinder:
    """Test contact/email finding against real sites."""

    @pytest.mark.asyncio
    async def test_find_contacts_example(self):
        """Find contacts on a real page."""
        collector = ContactCollector()
        result = await collector.collect(TEST_SITES["example"])
        # example.com has no contacts, but should not crash
        assert isinstance(result, dict)


class TestLiveFailureTracking:
    """Test that failure tracking works with real errors."""

    @pytest.mark.asyncio
    async def test_robots_blocked(self):
        """Verify robots.txt check raises PermissionError."""
        async with Scraper(respect_robots=True, use_stealth=False, use_captcha_solver=False, use_rotator=False) as s:
            with pytest.raises(PermissionError, match="robots.txt"):
                await s.scrape("https://www.google.com/search?q=test")

    @pytest.mark.asyncio
    async def test_invalid_url_graceful(self):
        """Invalid URL should raise, not crash."""
        async with Scraper(use_stealth=False, use_captcha_solver=False, use_rotator=False, track_failures=True) as s:
            with pytest.raises(Exception):
                await s.scrape("https://this-domain-does-not-exist-12345.com")
            if s.failure_tracker:
                failures = s.failure_tracker.get_failed_urls()
                assert len(failures) > 0


class TestLiveCache:
    """Test caching behavior with real requests."""

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Second request should be cached."""
        async with Scraper(use_stealth=False, use_captcha_solver=False, use_rotator=False, cache_ttl=60) as s:
            r1 = await s.scrape(TEST_SITES["example"])
            r2 = await s.scrape(TEST_SITES["example"])
            assert r1["content"]
            assert r2["content"]
            assert r1["timestamp"] == r2["timestamp"]
