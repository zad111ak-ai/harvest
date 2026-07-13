"""Extract — Structured data extraction from web pages using CSS selectors or LLM.

Uses Scrapling + beautifulsoup4 for HTML parsing.
Optional LLM-based extraction via OpenAI-compatible API (OmniRoute, Ollama, etc.).

Features:
- Pydantic validation with auto-retry on invalid LLM responses
- Token usage tracking per request
- Smart HTML preprocessing to reduce token costs
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Optional

import aiohttp
from bs4 import BeautifulSoup
from pydantic import BaseModel, ValidationError

from .core import Scraper
from .preprocess import clean_html_for_llm

log = logging.getLogger("harvest.extract")

# Default LLM endpoint (OmniRoute or any OpenAI-compatible)
DEFAULT_LLM_URL = "http://localhost:3000/v1"
DEFAULT_LLM_MODEL = "auto/best-chat"

# Token costs per 1M tokens (USD) — common models
TOKEN_COSTS = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
}


class TokenUsage:
    """Track token usage and estimated costs."""

    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.requests = 0
        self.model = ""

    def record(self, input_tokens: int, output_tokens: int, model: str = ""):
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.requests += 1
        if model:
            self.model = model

    def estimate_cost(self) -> float:
        """Estimate cost in USD based on known model pricing."""
        costs = TOKEN_COSTS.get(self.model, {"input": 3.00, "output": 10.00})
        return (self.input_tokens * costs["input"] + self.output_tokens * costs["output"]) / 1_000_000

    def summary(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "requests": self.requests,
            "estimated_cost_usd": round(self.estimate_cost(), 4),
        }


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

    Features:
    - Pydantic validation with auto-retry on invalid responses
    - Token usage tracking and cost estimation
    - Smart HTML preprocessing to reduce token costs

    Works with any OpenAI-compatible API (OmniRoute, Ollama, OpenAI, etc.).

    Examples:
        from pydantic import BaseModel

        class Product(BaseModel):
            name: str
            price: float
            currency: str = "USD"

        extractor = LLMExtractor()
        result = await extractor.extract(
            url="https://shop.example.com/item/123",
            description="Extract the product name, price and currency",
            pydantic_model=Product,
        )
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
        self.token_usage = TokenUsage()

    async def _get_session(self):
        if self._http_session is None:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    async def extract(
        self,
        url: str,
        description: str,
        schema: Optional[dict] = None,
        pydantic_model: Optional[type[BaseModel]] = None,
        extraction: str = "markdown",
        preprocess: bool = True,
    ) -> dict:
        """Extract data from a URL using natural language.

        Args:
            url: The page URL
            description: What to extract (e.g. "find all product prices and names")
            schema: Optional JSON schema to enforce structured output
            pydantic_model: Optional Pydantic model for response validation
            extraction: Page content format ('markdown', 'text', or 'html')
            preprocess: Clean HTML before sending to LLM (default True, saves tokens)

        Returns:
            dict with original page info + LLM extraction result
        """
        result = await self.scraper.scrape(url, extraction=extraction)
        content = result.get("content", "")

        if not content:
            return {"url": url, "error": "No content extracted from page"}

        # Smart preprocessing to reduce token costs
        if preprocess and extraction == "html":
            content = clean_html_for_llm(content, max_chars=50_000)
        else:
            content = content[:15_000]

        prompt = self._build_prompt(description, content, schema)
        extracted = await self._call_llm(prompt, schema, pydantic_model=pydantic_model)

        return {
            "url": url,
            "title": result.get("title", ""),
            "description": description,
            "extracted": extracted,
            "token_usage": self.token_usage.summary(),
            "timestamp": result.get("timestamp", ""),
        }

    async def extract_many(
        self,
        urls: list[str],
        description: str,
        schema: Optional[dict] = None,
        pydantic_model: Optional[type[BaseModel]] = None,
        extraction: str = "markdown",
    ) -> list[dict]:
        """Extract data from multiple URLs with the same description."""
        tasks = [self.extract(url, description, schema, pydantic_model, extraction) for url in urls]
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

    async def _call_llm(
        self,
        prompt: str,
        schema: Optional[dict] = None,
        pydantic_model: Optional[type[BaseModel]] = None,
        max_retries: int = 2,
    ) -> Any:
        """Call LLM with optional Pydantic validation and auto-retry on invalid JSON.

        If pydantic_model is provided, the response is validated against it.
        On validation failure, the error is sent back to the LLM for correction.
        """
        session = await self._get_session()
        messages: list[dict] = [{"role": "user", "content": prompt}]
        last_msg = ""

        for attempt in range(max_retries + 1):
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 4096,
            }
            if schema or pydantic_model:
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

                    # Track token usage
                    usage = data.get("usage", {})
                    self.token_usage.record(
                        input_tokens=usage.get("prompt_tokens", 0),
                        output_tokens=usage.get("completion_tokens", 0),
                        model=self.model,
                    )

                    msg = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    last_msg = msg = msg.strip()
                    if msg.startswith("```"):
                        msg = msg.split("```")[1]
                        if msg.startswith("json"):
                            msg = msg[4:]

                    parsed = json.loads(msg)

                    # Pydantic validation
                    if pydantic_model:
                        try:
                            validated = pydantic_model(**parsed)
                            return validated.model_dump()
                        except ValidationError as ve:
                            if attempt < max_retries:
                                log.warning(f"Pydantic validation failed (attempt {attempt + 1}): {ve}")
                                messages.append({"role": "assistant", "content": last_msg})
                                messages.append(
                                    {
                                        "role": "user",
                                        "content": f"Your JSON is invalid. Error: {ve.errors()[:3]}. Fix and return valid JSON only.",
                                    }
                                )
                                continue
                            return {"raw": parsed, "validation_error": str(ve)}

                    return parsed
            except json.JSONDecodeError:
                if attempt < max_retries:
                    messages.append({"role": "assistant", "content": last_msg})
                    messages.append(
                        {
                            "role": "user",
                            "content": "You returned invalid JSON. Return ONLY a valid JSON object.",
                        }
                    )
                    continue
                return {"raw": last_msg}
            except Exception as e:
                return {"error": f"LLM call failed: {str(e)}"}

        return {"error": "LLM extraction failed after all retries"}

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
