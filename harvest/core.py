"""
Core — Page scraping and content extraction.
"""
import re
import json
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse

from .browser import BrowserSession


class Scraper:
    """Extract structured content from any web page.

    Handles Cloudflare, JS rendering, anti-bot protections.
    """

    def __init__(self, proxy: Optional[str] = None, headless: bool = True):
        self.proxy = proxy
        self.headless = headless

    async def scrape(
        self,
        url: str,
        selector: Optional[str] = None,
        extraction: str = "markdown",
    ) -> dict:
        """Scrape a single URL.

        Args:
            url: The page URL
            selector: Optional CSS selector to extract specific elements
            extraction: 'markdown', 'text', or 'html'

        Returns:
            dict with url, title, content, metadata
        """
        async with BrowserSession(proxy=self.proxy, headless=self.headless) as session:
            resp = await session.fetch(
                url,
                extraction_type=extraction,
                main_content_only=(selector is None),
            )

        content = ""
        title = ""
        # Scrapling Response object
        if hasattr(resp, "body"):
            body = resp.body
            if isinstance(body, bytes):
                content = body.decode("utf-8", errors="replace")
            elif isinstance(body, str):
                content = body
            # Try prettify HTML
            try:
                pretty = resp.prettify()
                if pretty and len(pretty) > len(content):
                    content = pretty
            except Exception:
                pass
        elif isinstance(resp, dict):
            content = resp.get("content", "") or ""
            content = "\n".join(content) if isinstance(content, list) else str(content)
        elif isinstance(resp, str):
            content = resp

        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", content, re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()

        return {
            "url": url,
            "title": title or url,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def scrape_many(
        self, urls: list[str], selector: Optional[str] = None, extraction: str = "markdown"
    ) -> list[dict]:
        """Scrape multiple URLs concurrently."""
        import asyncio

        tasks = [self.scrape(url, selector, extraction) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                output.append({"url": urls[i], "error": str(r), "timestamp": datetime.utcnow().isoformat()})
            else:
                output.append(r)
        return output

    async def browse(self, url: str, page_action: callable) -> Any:
        """Execute a custom page_action on a page (login, click, etc)."""
        async with BrowserSession(proxy=self.proxy, headless=self.headless) as session:
            return await session.fetch(url, page_action=page_action)
