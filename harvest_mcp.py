"""Harvest MCP Server — Model Context Protocol interface for Harvest.

Exposes Harvest's web collection tools as MCP tools for AI agents.
Every Hermes/Claude/Cursor client can use it.

Usage:
    pip install harvest[mcp]
    hermes mcp add harvest --command 'harvest-mcp'
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("harvest-mcp")


# ---- Config ----
def _load_config() -> dict[str, Any]:
    """Load optional config from ~/.harvest/config.yaml."""
    config_path = Path.home() / ".harvest" / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


# ---- Server ----
def create_server():
    """Create and configure the Harvest MCP server."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("Harvest")
    cfg = _load_config()

    # Defaults from config
    default_proxy = cfg.get("proxy")
    default_headless = cfg.get("headless", True)

    # ---- Tool: scrape ----
    @mcp.tool()
    async def scrape(
        url: str,
        selector: Optional[str] = None,
        extraction: str = "markdown",
    ) -> str:
        """Scrape a web page and return its content.

        Args:
            url: The page URL to scrape.
            selector: Optional CSS selector to extract specific elements.
            extraction: Content format — 'markdown', 'text', or 'html'.

        Returns:
            Page content as text (markdown/text/html).
        """
        from harvest.core import Scraper

        scraper = Scraper(proxy=default_proxy, headless=default_headless)
        result = await scraper.scrape(url, selector=selector, extraction=extraction)
        content = result.get("content", "")
        return content[:500_000]  # Cap at 500K chars

    # ---- Tool: extract ----
    @mcp.tool()
    async def extract(
        url: str,
        schema: str = "",
    ) -> str:
        """Extract structured data from a page using a CSS selector schema.

        Schema format:
            Simple:     {"title": "h1", "price": ".price"}
            Attribute:  {"link": {"selector": "a.btn", "attr": "href"}}
            List:       {"items": {"_type": "list", "_selector": ".item",
                                   "name": ".name", "price": ".price"}}
            All by tag: {"links": "a._all_"}

        Args:
            url: The page URL.
            schema: JSON string of the extraction schema.

        Returns:
            Extracted data as JSON string.
        """
        from harvest.extract import SchemaExtractor

        schema_dict: dict = {}
        if schema:
            try:
                schema_dict = json.loads(schema)
            except json.JSONDecodeError as e:
                return json.dumps({"error": f"Invalid schema JSON: {e}"})

        if not schema_dict:
            return json.dumps({"error": "No schema provided"})

        ex = SchemaExtractor(proxy=default_proxy, headless=default_headless)
        result = await ex.extract(url, schema_dict)
        return json.dumps(result, ensure_ascii=False, indent=2)[:500_000]

    # ---- Tool: batch ----
    @mcp.tool()
    async def batch(
        urls: list[str],
        selector: Optional[str] = None,
        concurrency: int = 5,
    ) -> str:
        """Process multiple URLs concurrently.

        Args:
            urls: List of URLs to process.
            selector: Optional CSS selector.
            concurrency: Max concurrent requests (default 5).

        Returns:
            Batch results as JSON string.
        """
        from harvest.batch import BatchProcessor

        bp = BatchProcessor(
            concurrency=concurrency,
            proxy=default_proxy,
            headless=default_headless,
        )
        result = await bp.process_urls(urls, selector=selector)

        import dataclasses

        data = dataclasses.asdict(result)
        data.pop("results", None)
        data.pop("errors", None)
        return json.dumps(data, ensure_ascii=False, indent=2)

    # ---- Tool: contacts ----
    @mcp.tool()
    async def contacts(
        url: str,
        depth: int = 2,
    ) -> str:
        """Collect contact information (emails, social links) from a website.

        Args:
            url: Website URL to scan.
            depth: How many internal pages to check (1=home only).

        Returns:
            Contact data as JSON string.
        """
        from harvest.contacts import ContactCollector

        cc = ContactCollector()
        result = await cc.collect(url, depth=depth)
        return json.dumps(result, ensure_ascii=False, indent=2)[:500_000]

    # ---- Tool: crawl ----
    @mcp.tool()
    async def crawl(
        url: str,
        max_pages: int = 20,
        same_domain: bool = True,
    ) -> str:
        """Crawl a website and extract content from discovered pages.

        Args:
            url: Starting URL.
            max_pages: Max pages to scrape (default 20).
            same_domain: Stay on the same domain (default True).

        Returns:
            Crawl results as JSON string.
        """
        from harvest.crawl import SiteCrawler

        crawler = SiteCrawler(
            proxy=default_proxy,
            headless=default_headless,
        )
        result = await crawler.crawl(
            url,
            max_pages=max_pages,
            same_domain=same_domain,
        )
        # Truncate pages to avoid huge responses
        if "pages" in result:
            result["pages"] = result["pages"][:20]
            for p in result["pages"]:
                if "content" in p and len(p["content"]) > 10_000:
                    p["content"] = p["content"][:10_000] + "…"
        return json.dumps(result, ensure_ascii=False, indent=2)[:500_000]

    # ---- Tool: monitor ----
    @mcp.tool()
    async def monitor(
        url: str,
        selector: Optional[str] = None,
    ) -> str:
        """Check a page for changes since the last check.

        Stores snapshots in ~/.harvest/ for diff comparison.
        First call always returns 'no previous data'.

        Args:
            url: Page URL to monitor.
            selector: Optional CSS selector to narrow the monitored area.

        Returns:
            Monitor result as JSON string (changed, diff_text, etc.).
        """
        from harvest.monitor import ChangeWatcher

        cw = ChangeWatcher()
        result = await cw.check(url, selector=selector)
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ---- Tool: llm_extract ----
    @mcp.tool()
    async def llm_extract(
        url: str,
        prompt: str,
        schema: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """Extract structured data from a web page using natural language.

        No CSS selectors needed — just describe what you want in plain language.
        Uses a local LLM (OmniRoute, Ollama, or any OpenAI-compatible API).

        Args:
            url: The page URL to extract data from.
            prompt: What to extract in plain language (e.g. "get all product names and prices").
            schema: Optional JSON schema to enforce structured output.
            model: Optional LLM model override.

        Returns:
            Extracted data as JSON string.
        """
        from harvest.extract import LLMExtractor

        llm_cfg = cfg.get("llm", {})
        extractor = LLMExtractor(
            base_url=llm_cfg.get("base_url", "http://localhost:3000/v1"),
            model=model or llm_cfg.get("model", "auto/best-chat"),
            api_key=llm_cfg.get("api_key", "sk-omniroute"),
            proxy=default_proxy,
            headless=default_headless,
        )

        schema_dict = None
        if schema:
            try:
                schema_dict = json.loads(schema)
            except json.JSONDecodeError as e:
                return json.dumps({"error": f"Invalid schema JSON: {e}"})

        result = await extractor.extract(
            url=url,
            description=prompt,
            schema=schema_dict,
        )
        await extractor.close()
        return json.dumps(result, ensure_ascii=False, indent=2)[:500_000]

    # ---- Tool: map ----
    @mcp.tool()
    async def map_urls(
        url: str,
        max_urls: int = 500,
    ) -> str:
        """Discover all URLs on a website instantly.

        Uses sitemap.xml, robots.txt, and homepage links.
        Like Firecrawl Map — fast URL discovery without scraping content.

        Args:
            url: Website URL to discover.
            max_urls: Max URLs to return (default 500).

        Returns:
            JSON with discovered URLs.
        """
        import re
        from urllib.parse import urljoin, urlparse
        from bs4 import BeautifulSoup

        parsed = urlparse(url)
        domain = parsed.netloc
        urls = set()

        from harvest.core import Scraper

        scraper = Scraper(proxy=default_proxy, headless=default_headless)

        # 1. Sitemap.xml
        for surl in [urljoin(url, "/sitemap.xml"), urljoin(url, "/sitemap_index.xml")]:
            try:
                result = await scraper.scrape(surl, extraction="text")
                found = re.findall(r"https?://[^\s<>\"']+", result.get("content", ""))
                for u in found:
                    if domain in u:
                        urls.add(u.split("#")[0].split("?")[0])
            except Exception:
                continue

        # 2. robots.txt Sitemap directives
        try:
            robots = await scraper.scrape(f"{parsed.scheme}://{domain}/robots.txt", extraction="text")
            for line in robots.get("content", "").split("\n"):
                if line.lower().startswith("sitemap:"):
                    sm_url = line.split(":", 1)[1].strip()
                    sm = await scraper.scrape(sm_url, extraction="text")
                    for u in re.findall(r"https?://[^\s<>\"']+", sm.get("content", "")):
                        if domain in u:
                            urls.add(u.split("#")[0].split("?")[0])
        except Exception:
            pass

        # 3. Homepage links
        try:
            home = await scraper.scrape(url, extraction="html")
            soup = BeautifulSoup(home.get("content", ""), "html.parser")
            for a in soup.find_all("a", href=True):
                href = urljoin(url, str(a["href"])).split("#")[0].split("?")[0]
                if domain in href:
                    urls.add(href)
        except Exception:
            pass

        url_list = sorted(urls)[:max_urls]
        return json.dumps({"domain": domain, "total": len(url_list), "urls": url_list}, ensure_ascii=False, indent=2)

    # ---- Tool: status ----
    @mcp.tool()
    def status() -> str:
        """Get Harvest system status and configuration.

        Returns:
            Status info as JSON string.
        """
        return json.dumps(
            {
                "version": "0.6.2",
                "proxy_configured": bool(default_proxy),
                "headless": default_headless,
                "config_file": str(Path.home() / ".harvest" / "config.yaml"),
                "tools": [
                    "scrape",
                    "extract",
                    "llm_extract",
                    "map_urls",
                    "batch",
                    "contacts",
                    "crawl",
                    "monitor",
                    "status",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )

    return mcp


# ---- Entry point ----
def main():
    """Run the Harvest MCP server on stdio."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s | %(name)s | %(message)s",
    )

    import sys

    if "--version" in sys.argv:
        print("Harvest MCP Server 0.6.1")
        return

    mcp = create_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
