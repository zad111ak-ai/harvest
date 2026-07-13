"""Extract — Structured data extraction from web pages using CSS selectors or LLM.

Uses Scrapling + beautifulsoup4 for HTML parsing.
Optional LLM-based extraction via OpenAI-compatible API (OmniRoute, Ollama, etc.).
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

import aiohttp
from bs4 import BeautifulSoup

from .core import Scraper


# Default LLM endpoint (OmniRoute or any OpenAI-compatible)
DEFAULT_LLM_URL = "http://localhost:3000/v1"
DEFAULT_LLM_MODEL = "auto/best-chat"


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
        tasks = [self.extract(url, schema, extraction) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def _extract_field(self, soup: BeautifulSoup, field_def: Any) -> Any:
        if isinstance(field_def, str):
            return self._css_text(soup, field_def)
        if isinstance(field_def, dict):
            sel = field_def.get("_selector", field_def.get("selector", ""))
            _type = field_def.get("_type", "single")
            if _type == "list":
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
            attr = field_def.get("attr", "text")
            many = field_def.get("many", False)
            if many:
                return self._css_all_attr(soup, sel, attr)
            return self._css_attr(soup, sel, attr)
        return None

    def _css_text(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else None

    def _css_all(self, soup: BeautifulSoup, selector: str) -> list[str]:
        return [el.get_text(strip=True) for el in soup.select(selector)]

    def _css_attr(self, soup: BeautifulSoup, selector: str, attr: str) -> Optional[str]:
        el = soup.select_one(selector)
        if not el:
            return None
        if attr == "text":
            return el.get_text(strip=True)
        return el.get(attr)

    def _css_all_attr(self, soup: BeautifulSoup, selector: str, attr: str) -> list[Any]:
        results = []
        for el in soup.select(selector):
            if attr == "text":
                results.append(el.get_text(strip=True))
            else:
                results.append(el.get(attr))
        return results


class LLMExtractor:
    """Extract structured data from web pages using natural language + LLM.

    No CSS selectors needed — just describe what you want.

    Works with any OpenAI-compatible API (OmniRoute, Ollama, OpenAI, etc.).

    Examples:
        extractor = LLMExtractor()
        result = await extractor.extract(
            url="https://news.ycombinator.com",
            description="Get the top 10 story titles and their points",
        )
        # Returns: {"url": "...", "title": "...", "extracted": [...], ...}
    """

    def __init__(
        self,
        base_url: str = DEFAULT_LLM_URL,
        model: str = DEFAULT_LLM_MODEL,
        api_key: str = "sk-omniroute",
        proxy: Optional[str] = None,
        headless: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.scraper = Scraper(proxy=proxy, headless=headless)
        self._http_session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self):
        if self._http_session is None:
            import aiohttp

            self._http_session = aiohttp.ClientSession()
        return self._http_session

    async def extract(
        self,
        url: str,
        description: str,
        schema: Optional[dict] = None,
        extraction: str = "markdown",
    ) -> dict:
        """Extract data from a URL using natural language.

        Args:
            url: The page URL
            description: What to extract (e.g. "find all product prices and names")
            schema: Optional JSON schema to enforce structured output
            extraction: Page content format to feed to LLM ('markdown', 'text', or 'html')

        Returns:
            dict with original page info + LLM extraction result
        """
        # Scrape the page first
        result = await self.scraper.scrape(url, extraction=extraction)
        content = result.get("content", "")

        if not content:
            return {
                "url": url,
                "error": "No content extracted from page",
            }

        # Truncate content to avoid token limits
        content = content[:15000]

        # Build prompt
        prompt = self._build_prompt(description, content, schema)

        # Call LLM
        extracted = await self._call_llm(prompt, schema)

        return {
            "url": url,
            "title": result.get("title", ""),
            "description": description,
            "extracted": extracted,
            "timestamp": result.get("timestamp", ""),
        }

    async def extract_many(
        self,
        urls: list[str],
        description: str,
        schema: Optional[dict] = None,
        extraction: str = "markdown",
    ) -> list[dict]:
        """Extract data from multiple URLs with the same description."""
        tasks = [self.extract(url, description, schema, extraction) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def _build_prompt(self, description: str, content: str, schema: Optional[dict] = None) -> str:
        prompt = f"""Extract the following information from the web page content below.

Extraction task: {description}

Page content:
---
{content}
---

Return ONLY a valid JSON object with the extracted data.
"""
        if schema:
            prompt += f"\nUse this JSON schema:\n{json.dumps(schema, indent=2)}\n"
        else:
            prompt += "\nUse any structure that best fits the data.\n"

        return prompt

    async def _call_llm(self, prompt: str, schema: Optional[dict] = None) -> Any:
        session = await self._get_session()

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        # Try structured output if schema is provided (OpenAI-compatible)
        if schema:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return {"error": f"LLM API error {resp.status}: {text[:200]}"}
                data = await resp.json()
                msg = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                # Try to parse JSON from the response
                msg = msg.strip()
                if msg.startswith("```"):
                    msg = msg.split("```")[1]
                    if msg.startswith("json"):
                        msg = msg[4:]
                try:
                    return json.loads(msg)
                except json.JSONDecodeError:
                    return {"raw": msg}
        except Exception as e:
            return {"error": f"LLM call failed: {str(e)}"}

    async def close(self):
        if self._http_session:
            await self._http_session.close()
            self._http_session = None


def load_schema(schema_src: str) -> dict:
    """Load schema from string or file reference."""
    if schema_src.startswith("file://"):
        path = Path(schema_src[7:])
        with open(path) as f:
            return json.load(f)
    return json.loads(schema_src)
