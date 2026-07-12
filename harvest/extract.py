"""Extract — Structured data extraction from web pages using CSS selectors.

Uses Scrapling + beautifulsoup4 for real HTML parsing (not regex).
"""

import json
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup

from .core import Scraper


class SchemaExtractor:
    """Extract structured data from web pages using CSS selector schemas.

    Schema formats:
        Simple:         {"field_name": "css_selector"}
        Text attr:      {"field_name": {"selector": "css", "attr": "href"}}
        List of items:  {"field_name": {"_type": "list", "_selector": ".item",
                                         "title": ".title", "price": ".price"}}
        All of type:    {"field_name": "._all_selector"}

    The schema is evaluated using BeautifulSoup on the HTML.
    """

    def __init__(self, proxy: Optional[str] = None, headless: bool = True):
        self.scraper = Scraper(proxy=proxy, headless=headless)

    async def extract(
        self,
        url: str,
        schema: dict,
        extraction: str = "html",
        selector: Optional[str] = None,
    ) -> dict:
        """Extract structured data from a URL using a schema."""
        result = await self.scraper.scrape(url, selector=selector, extraction="html")
        content = result.get("content", "")

        soup = BeautifulSoup(content, "html.parser")
        extracted = {}

        for field_name, field_def in schema.items():
            extracted[field_name] = self._extract_field(soup, field_def)

        return {
            "url": url,
            "title": result.get("title", ""),
            "extracted": extracted,
            "timestamp": result.get("timestamp", ""),
        }

    async def extract_many(self, urls: list[str], schema: dict, extraction: str = "html") -> list[dict]:
        import asyncio

        tasks = [self.extract(url, schema, extraction) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def _extract_field(self, soup: BeautifulSoup, field_def: Any) -> Any:
        if isinstance(field_def, str):
            # Simple CSS selector → inner text
            return self._css_text(soup, field_def)

        if isinstance(field_def, dict):
            sel = field_def.get("_selector", field_def.get("selector", ""))
            _type = field_def.get("_type", "single")

            if _type == "list":
                # List of items: find container, extract fields from each
                containers = soup.select(sel) if sel else [soup]
                results = []
                fields = {k: v for k, v in field_def.items() if not k.startswith("_")}
                for c in containers:
                    item = {}
                    for fn, fd in fields.items():
                        item[fn] = self._extract_field(c, fd)
                    results.append(item)
                return results

            if _type == "all":
                return self._css_all(soup, sel)

            # Single field with optional attr
            attr = field_def.get("attr", "text")
            many = field_def.get("many", False)
            if many:
                return self._css_all_attr(soup, sel, attr)
            return self._css_attr(soup, sel, attr)

        return None

    def _css_text(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        """Get inner text of first matching element."""
        el = soup.select_one(selector)
        if el:
            return el.get_text(strip=True)
        return None

    def _css_all(self, soup: BeautifulSoup, selector: str) -> list[str]:
        """Get inner texts of all matching elements."""
        return [el.get_text(strip=True) for el in soup.select(selector)]

    def _css_attr(self, soup: BeautifulSoup, selector: str, attr: str) -> Optional[str]:
        """Get attribute from first matching element."""
        el = soup.select_one(selector)
        if el:
            if attr == "text":
                return el.get_text(strip=True)
            return el.get(attr)
        return None

    def _css_all_attr(self, soup: BeautifulSoup, selector: str, attr: str) -> list[Any]:
        """Get attribute from all matching elements."""
        results = []
        for el in soup.select(selector):
            if attr == "text":
                results.append(el.get_text(strip=True))
            else:
                results.append(el.get(attr))
        return results


def load_schema(schema_src: str) -> dict:
    """Load schema from string or file reference."""
    if schema_src.startswith("file://"):
        path = Path(schema_src[7:])
        with open(path) as f:
            return json.load(f)
    return json.loads(schema_src)
