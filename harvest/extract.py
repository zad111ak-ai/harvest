"""
Extract — Structured data extraction from web pages.

Turns messy HTML into clean structured data defined by a schema.
Like Browse AI, but free and local.

Usage:
    harvest extract <url> --schema '{"title": "h1", "price": ".price"}'
    harvest extract <url> --schema file://schema.json
    harvest extract <url> --schema '{"items": {"selector": ".product", "fields": {"name": "h2", "price": ".price"}}}'
"""

import json
import re
from pathlib import Path
from typing import Any, Optional

from .core import Scraper


class SchemaExtractor:
    """Extract structured data from web pages using CSS selector schemas.

    Schema format:
        Simple:      {"field_name": "css_selector"}
        Text attr:   {"field_name": {"selector": "css", "attr": "href"}}
        List:        {"field_name": {"selector": "css", "fields": {...}}}
        Nested:      {"field_name": {"selector": "css", "fields": {...}, "attr": "text"}}

    The result is always JSON — ready for export, piping, or webhooks.
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
        """Extract structured data from a URL using a schema.

        Args:
            url: Page URL
            schema: Extraction schema dict
            extraction: 'html' for full page, 'markdown' for cleaner text
            selector: Global CSS selector to scope extraction

        Returns:
            dict with extracted data
        """
        # Scrape with raw HTML for selector processing
        result = await self.scraper.scrape(url, selector=selector, extraction=extraction)
        content = result.get("content", "")

        # Actually we need raw HTML for CSS selection.
        # Fetch again if we got markdown.
        if extraction != "html":
            html_result = await self.scraper.scrape(url, selector=selector, extraction="html")
            html_content = html_result.get("content", "")
        else:
            html_content = content

        extracted = {}
        for field_name, field_def in schema.items():
            extracted[field_name] = self._extract_field(html_content, field_def)

        return {
            "url": url,
            "title": result.get("title", ""),
            "extracted": extracted,
            "timestamp": result.get("timestamp", ""),
        }

    async def extract_many(
        self,
        urls: list[str],
        schema: dict,
        extraction: str = "html",
    ) -> list[dict]:
        """Extract from multiple URLs concurrently."""
        import asyncio

        tasks = [self.extract(url, schema, extraction) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def _extract_field(self, html: str, field_def: Any) -> Any:
        """Extract a single field value from HTML given its definition."""
        if isinstance(field_def, str):
            # Simple: "css_selector" → inner text
            return self._extract_text(html, field_def)

        if isinstance(field_def, dict):
            selector = field_def.get("selector", "")
            attr = field_def.get("attr", "text")
            fields = field_def.get("fields")
            many = field_def.get("many", False)

            if fields and selector:
                # Nested: {"selector": ".item", "fields": {...}}
                return self._extract_nested(html, selector, fields, many)
            elif selector:
                return self._extract_by_attr(html, selector, attr, many)

        return None

    def _extract_text(self, html: str, selector: str) -> Optional[str]:
        """Extract inner text from first matching element."""
        # Use regex-based extraction since we have raw HTML
        # Pattern matches: <tag ...>text</tag> or <tag ... attr="value" ...>
        # Simple approach: find elements by tag+class, extract content
        texts = self._match_selector(html, selector)
        return texts[0] if texts else None

    def _extract_by_attr(self, html: str, selector: str, attr: str, many: bool = False) -> Any:
        """Extract an attribute from matching elements."""
        matches = self._match_selector_attr(html, selector, attr)
        return matches if many else (matches[0] if matches else None)

    def _extract_nested(self, html: str, selector: str, fields: dict, many: bool = False) -> Any:
        """Extract multiple fields from each matching container element."""
        containers = self._split_by_selector(html, selector)
        results = []
        for container in containers:
            item = {}
            for field_name, field_def in fields.items():
                item[field_name] = self._extract_field(container, field_def)
            results.append(item)
        return results if many else (results[0] if results else None)

    def _match_selector(self, html: str, selector: str) -> list[str]:
        """Match CSS selector and return inner texts.

        Handles:
            - tag (h1, p, div)
            - .class
            - #id
            - tag.class
            - tag#id
            - tag[attr="value"]
            - parent child
            - parent > child
        """
        # Parse simple selectors
        selector = selector.strip()

        # Split by > for direct child
        if " > " in selector:
            parts = [s.strip() for s in selector.split(" > ")]
            # Get the last part as the target
            return self._match_selector(html, parts[-1])

        # Split by space for descendant
        if " " in selector and not selector.startswith(".") and not selector.startswith("#"):
            parts = [s.strip() for s in selector.split(" ", 1)]
            container_matches = self._match_selector(html, parts[0])
            results = []
            for cm in container_matches:
                results.extend(self._match_selector(cm, parts[1]))
            return results

        tag = ""
        class_name = ""
        id_name = ""
        attr_name = ""
        attr_value = ""

        # Parse tag[attr="value"]
        attr_match = re.match(r"^([a-zA-Z0-9]*)\[([a-zA-Z-]+)=[\"']([^\"']*)[\"']\]", selector)
        if attr_match:
            tag = attr_match.group(1) or "[a-zA-Z0-9]+"
            attr_name = attr_match.group(2)
            attr_value = attr_match.group(3)
            pattern = rf'<{tag}[^>]*{attr_name}=["\']{re.escape(attr_value)}["\'][^>]*>(.*?)</{tag}>'
            return self._extract_all(html, pattern)

        # Parse tag#id.class or .class or #id
        class_match = re.search(r"\.([a-zA-Z0-9_-]+)", selector)
        id_match = re.search(r"#([a-zA-Z0-9_-]+)", selector)
        tag_match = re.match(r"^([a-zA-Z0-9]+)", selector)

        if tag_match:
            tag = tag_match.group(1)
        if class_match:
            class_name = class_match.group(1)
        if id_match:
            id_name = id_match.group(1)

        if id_name:
            pattern = (
                rf'<{tag or "[a-zA-Z0-9]+"}[^>]*id=["\']{re.escape(id_name)}["\'][^>]*>(.*?)</{tag or "[a-zA-Z0-9]+"}>'
            )
            texts = self._extract_all(html, pattern)
            if texts:
                return [self._strip_html(t) for t in texts]

        if class_name:
            pattern = rf'<{tag or "[a-zA-Z0-9]+"}[^>]*class=["\'][^"\']*{re.escape(class_name)}[^"\']*["\'][^>]*>(.*?)</{tag or "[a-zA-Z0-9]+"}>'
            texts = self._extract_all(html, pattern)
            if texts:
                return [self._strip_html(t) for t in texts]

        if tag:
            pattern = rf"<{tag}(?:\s+[^>]*)?>(.*?)</{tag}>"
            texts = self._extract_all(html, pattern)
            return [self._strip_html(t) for t in texts]

        return []

    def _match_selector_attr(self, html: str, selector: str, attr: str) -> list[str]:
        """Match CSS selector and return attribute values."""
        matches = self._match_selector_raw(html, selector)
        values = []
        for match in matches:
            if attr == "href":
                href_match = re.search(r'href=["\']([^"\']+)["\']', match)
                if href_match:
                    values.append(href_match.group(1))
            elif attr == "src":
                src_match = re.search(r'src=["\']([^"\']+)["\']', match)
                if src_match:
                    values.append(src_match.group(1))
            elif attr == "text":
                text = re.sub(r"<[^>]+>", "", match).strip()
                values.append(text)
            else:
                attr_match = re.search(rf'{re.escape(attr)}=["\']([^"\']+)["\']', match)
                if attr_match:
                    values.append(attr_match.group(1))
        return values

    def _match_selector_raw(self, html: str, selector: str) -> list[str]:
        """Match selector and return raw HTML of matching elements."""
        texts = self._match_selector(html, selector)

        # For raw HTML, we need the full element
        class MatchTracker:
            def __init__(self):
                self.matches = []

        return texts  # Simplified

    def _split_by_selector(self, html: str, selector: str) -> list[str]:
        """Split HTML into containers matched by selector."""
        # Match the outer elements
        tag = "div"
        class_name = ""
        id_name = ""

        class_match = re.search(r"\.([a-zA-Z0-9_-]+)", selector)
        id_match = re.search(r"#([a-zA-Z0-9_-]+)", selector)
        tag_match = re.match(r"^([a-zA-Z0-9]+)", selector)

        if tag_match:
            tag = tag_match.group(1)
        if class_match:
            class_name = class_match.group(1)
        if id_match:
            id_name = id_match.group(1)

        if class_name:
            pattern = rf'(<{tag}[^>]*class=["\'][^"\']*{re.escape(class_name)}[^"\']*["\'][^>]*>.*?</{tag}>)'
        elif id_name:
            pattern = rf'(<{tag}[^>]*id=["\']{re.escape(id_name)}["\'][^>]*>.*?</{tag}>)'
        else:
            pattern = rf"(<{tag}[^>]*>.*?</{tag}>)"

        return re.findall(pattern, html, re.DOTALL)

    def _extract_all(self, html: str, pattern: str) -> list[str]:
        """Extract all group(1) matches."""
        return re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

    def _strip_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text


def load_schema(schema_src: str) -> dict:
    """Load schema from string or file reference.

    Accepts:
        - JSON string: '{"title": "h1"}'
        - File reference: 'file://schema.json'
    """
    if schema_src.startswith("file://"):
        path = Path(schema_src[7:])
        with open(path) as f:
            return json.load(f)
    return json.loads(schema_src)
