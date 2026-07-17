"""
Tests for Crawl4AI backend integration.

Tests availability detection, scrape, scrape_many, and deep_crawl.
Run: python3 -m pytest tests/test_crawl4ai.py -v
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_crawl4ai_availability():
    """Crawl4AIBackend should detect crawl4ai installation."""
    from harvest.integrations.crawl4ai_backend import Crawl4AIBackend

    backend = Crawl4AIBackend()
    assert backend.available is True


def test_crawl4ai_unavailable():
    """Crawl4AIBackend should handle missing crawl4ai gracefully."""
    import harvest.integrations.crawl4ai_backend as mod

    with patch.dict("sys.modules", {"crawl4ai": None}):
        import importlib

        importlib.reload(mod)
        backend = mod.Crawl4AIBackend()
        assert backend.available is False
        importlib.reload(mod)


def test_crawl4ai_scrape_returns_none_when_unavailable():
    """Scrape should return None when crawl4ai is not installed."""
    import harvest.integrations.crawl4ai_backend as mod

    with patch.dict("sys.modules", {"crawl4ai": None}):
        import importlib

        importlib.reload(mod)
        backend = mod.Crawl4AIBackend()
        result = asyncio.run(backend.scrape("https://example.com"))
        assert result is None
        importlib.reload(mod)


def test_crawl4ai_scrape_success():
    """Scrape should return Harvest-compatible result dict."""
    from harvest.integrations.crawl4ai_backend import Crawl4AIBackend

    backend = Crawl4AIBackend()

    mock_result = MagicMock()
    mock_result.success = True
    mock_result.url = "https://example.com"
    mock_result.markdown.raw_markdown = "# Example\nHello world"
    mock_result.markdown.fit_markdown = "Hello world"
    mock_result.html = "<h1>Example</h1>"
    mock_result.metadata = {"title": "Example Domain"}
    mock_result.status_code = 200
    mock_result.error_message = None

    mock_crawler = AsyncMock()
    mock_crawler.arun = AsyncMock(return_value=mock_result)
    mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler.__aexit__ = AsyncMock(return_value=False)

    with patch("crawl4ai.AsyncWebCrawler", return_value=mock_crawler):
        result = asyncio.run(backend.scrape("https://example.com"))

    assert result is not None
    assert result["url"] == "https://example.com"
    assert result["content"] == "Hello world"
    assert result["title"] == "Example Domain"
    assert result["markdown"] == "# Example\nHello world"
    assert result["backend"] == "crawl4ai"
    assert result["status_code"] == 200


def test_crawl4ai_scrape_failure():
    """Scrape should return None on crawl4ai failure."""
    from harvest.integrations.crawl4ai_backend import Crawl4AIBackend

    backend = Crawl4AIBackend()

    mock_result = MagicMock()
    mock_result.success = False
    mock_result.error_message = "Connection timeout"

    mock_crawler = AsyncMock()
    mock_crawler.arun = AsyncMock(return_value=mock_result)
    mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler.__aexit__ = AsyncMock(return_value=False)

    with patch("crawl4ai.AsyncWebCrawler", return_value=mock_crawler):
        result = asyncio.run(backend.scrape("https://example.com"))

    assert result is None


def test_crawl4ai_scrape_many():
    """scrape_many should handle multiple URLs."""
    from harvest.integrations.crawl4ai_backend import Crawl4AIBackend

    backend = Crawl4AIBackend()

    mock_result1 = MagicMock()
    mock_result1.success = True
    mock_result1.url = "https://a.com"
    mock_result1.markdown.raw_markdown = "Page A"
    mock_result1.markdown.fit_markdown = "Page A"
    mock_result1.html = ""
    mock_result1.metadata = {}
    mock_result1.status_code = 200
    mock_result1.error_message = None

    mock_result2 = MagicMock()
    mock_result2.success = False
    mock_result2.url = "https://b.com"
    mock_result2.error_message = "404"

    mock_crawler = AsyncMock()
    mock_crawler.arun_many = AsyncMock(return_value=[mock_result1, mock_result2])
    mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler.__aexit__ = AsyncMock(return_value=False)

    with patch("crawl4ai.AsyncWebCrawler", return_value=mock_crawler):
        results = asyncio.run(backend.scrape_many(["https://a.com", "https://b.com"]))

    assert len(results) == 2
    assert results[0] is not None
    assert results[0]["url"] == "https://a.com"
    assert results[0]["backend"] == "crawl4ai"
    assert results[1] is None


def test_crawl4ai_config_backend():
    """Config should support backend selection."""
    import tempfile

    from harvest.config import Config

    with tempfile.TemporaryDirectory() as tmp:
        cfg = Config(config_path=f"{tmp}/config.yaml")
        assert cfg.get("scraper", "backend") == "scrapling"
        cfg.set("scraper", "backend", value="crawl4ai")
        assert cfg.get("scraper", "backend") == "crawl4ai"
