"""Script Generator — Generate standalone scraping scripts (zero LLM cost at runtime).

Analyzes a page with LLM once, then produces a self-contained Python script
that extracts the same data forever — 0 tokens per run.

Usage:
    gen = ScriptGenerator()
    script = await gen.generate(url="https://shop.com", fields=["title", "price", "image"])
    gen.save(script, "scrape_shop.py")
    # Now run:  python3 scrape_shop.py https://shop.com/product/123
"""

import json
import logging
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional


log = logging.getLogger("harvest.script_gen")

# ── LLM config (same as extract.py / self_healing.py) ───────────────────────
DEFAULT_LLM_URL = "http://localhost:3000/v1"
DEFAULT_LLM_MODEL = "auto/best-chat"
DEFAULT_LLM_KEY = "sk-omniroute"

# ── Prompt template ──────────────────────────────────────────────────────────
_ANALYSIS_PROMPT = """You are a web-scraping CSS selector expert.
Given the HTML of a page, find the BEST CSS selectors for each requested field.

URL: {url}
Requested fields: {fields}

HTML (structural sample):
{html}

Rules:
- Prefer short, stable selectors (classes > IDs > attributes).
- Avoid selectors tied to dynamic content (random class names).
- For list items, use a container selector + child selectors.
- Return ONLY valid JSON, no explanation.

Return format:
{{
  "selectors": {{
    "field_name": "css-selector",
    ...
  }},
  "list_container": "css-selector-for-repeating-items-or-null",
  "item_selectors": {{
    "field_name": "child-css-selector-relative-to-container",
    ...
  }},
  "pagination": {{
    "next_url": "css-selector-or-null",
    "next_attr": "href"
  }},
  "notes": "Brief explanation of selector strategy"
}}
"""


class ScriptGenerator:
    """Analyze a page and generate a standalone scraping script."""

    def __init__(
        self,
        llm_base_url: str = DEFAULT_LLM_URL,
        llm_model: str = DEFAULT_LLM_MODEL,
        llm_api_key: str = DEFAULT_LLM_KEY,
        proxy: Optional[str] = None,
    ):
        self.llm_base_url = llm_base_url
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        self.proxy = proxy

    def _fetch_html(self, url: str) -> str:
        """Fetch page HTML via Scrapling (bypasses Cloudflare)."""
        from scrapling import Fetcher

        fetcher = Fetcher()
        response = fetcher.get(url)
        if response and response.body:
            return response.body.decode("utf-8", errors="replace")
        return ""

    async def _analyze_with_llm(self, url: str, html: str, fields: list[str]) -> dict:
        """Send HTML to LLM to discover optimal CSS selectors."""
        import aiohttp

        prompt = _ANALYSIS_PROMPT.format(
            url=url,
            fields=json.dumps(fields),
            html=html[:15000],  # truncate to save tokens
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.llm_base_url}/chat/completions",
                json={
                    "model": self.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 2000,
                    "stream": False,
                },
                headers={
                    "Authorization": f"Bearer {self.llm_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                raw = await resp.read()
                body_str = raw.decode("utf-8", errors="replace")

                # Handle SSE (streaming) responses for models that don't do JSON mode
                # Try JSON first, fall back to SSE parsing
                try:
                    data = json.loads(body_str)
                except json.JSONDecodeError:
                    # SSE format — data: {...}
                    import re

                    json_blocks = re.findall(r"data:\s*(\{.*?\})(?:\n|$)", body_str, re.DOTALL)
                    if json_blocks:
                        last = json.loads(json_blocks[-1])
                        content = last.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if content:
                            # Parse JSON from content
                            json_str = content
                            if "```json" in content:
                                json_str = content.split("```json")[-1].split("```")[0]
                            elif "```" in content:
                                json_str = content.split("```")[-1].split("```")[0]
                            return json.loads(json_str.strip())
                    raise

                content = data["choices"][0]["message"]["content"]

                # Parse JSON from response (handle markdown code blocks)
                json_str = content
                if "```json" in content:
                    json_str = content.split("```json")[-1].split("```")[0]
                elif "```" in content:
                    json_str = content.split("```")[-1].split("```")[0]

                return json.loads(json_str.strip())

    async def generate(
        self,
        url: str,
        fields: list[str],
        output_format: str = "json",
        include_headers: bool = True,
        add_delay: bool = True,
    ) -> str:
        """Generate a standalone scraping script.

        Args:
            url: URL to analyze (will fetch and send to LLM).
            fields: Data fields to extract (e.g. ["title", "price", "image"]).
            output_format: "json" or "csv".
            include_headers: Add browser headers for stealth.
            add_delay: Add random delays between requests.

        Returns:
            Complete Python script as string.
        """
        log.info(f"Fetching {url} for analysis...")
        html = self._fetch_html(url)

        if not html:
            raise ValueError(f"Failed to fetch HTML from {url}")

        log.info(f"Analyzing with LLM ({len(html)} chars HTML)...")
        analysis = await self._analyze_with_llm(url, html, fields)

        selectors = analysis.get("selectors", {})
        list_container = analysis.get("list_container")
        item_selectors = analysis.get("item_selectors", {})
        pagination = analysis.get("pagination", {})
        notes = analysis.get("notes", "")

        # Validate selectors exist for all requested fields
        missing = [f for f in fields if f not in selectors and f not in item_selectors]
        if missing:
            log.warning(f"LLM did not provide selectors for: {missing}")

        script = self._build_script(
            url=url,
            fields=fields,
            selectors=selectors,
            list_container=list_container,
            item_selectors=item_selectors,
            pagination=pagination,
            output_format=output_format,
            include_headers=include_headers,
            add_delay=add_delay,
            notes=notes,
        )

        return script

    def _build_script(
        self,
        url: str,
        fields: list[str],
        selectors: dict[str, str],
        list_container: Optional[str],
        item_selectors: dict[str, str],
        pagination: dict[str, str],
        output_format: str,
        include_headers: bool,
        add_delay: bool,
        notes: str,
    ) -> str:
        """Build the standalone Python script."""

        # Selectors as JSON for embedding
        selectors_json = json.dumps(selectors, indent=8)
        item_json = json.dumps(item_selectors, indent=8) if item_selectors else "None"
        container = repr(list_container) if list_container else "None"
        next_sel = repr(pagination.get("next_url")) if pagination.get("next_url") else "None"
        next_attr = repr(pagination.get("next_attr", "href"))

        header_code = ""

        script = textwrap.dedent(f'''\
#!/usr/bin/env python3
"""
Auto-generated by Harvest Script Generator
Source: {url}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Fields: {", ".join(fields)}
Notes: {notes}

Usage:
    python3 this_script.py [URL]
    python3 this_script.py urls.txt   # batch: one URL per line
    python3 this_script.py urls.txt --csv output.csv
"""

import json
import random
import sys
import time
from pathlib import Path

from scrapling import Fetcher
from bs4 import BeautifulSoup
{header_code}

# ── Extracted selectors (LLM-optimized) ──
SELECTORS = {selectors_json}
ITEM_SELECTORS = {item_json}  # list mode: child selectors per container
LIST_CONTAINER = {container}

# ── Pagination ──
NEXT_URL_SELECTOR = {next_sel}
NEXT_ATTR = {next_attr}

FIELDS = {json.dumps(fields)}


def extract_from_html(html: str) -> list[dict] | dict:
    """Extract data from raw HTML using hardcoded selectors."""
    soup = BeautifulSoup(html, "html.parser")

    if LIST_CONTAINER and ITEM_SELECTORS:
        containers = soup.select(LIST_CONTAINER)
        results = []
        for container in containers:
            item = {{}}
            for field, sel in ITEM_SELECTORS.items():
                el = container.select_one(sel)
                item[field] = el.get_text(strip=True) if el else None
            results.append(item)
        return results
    else:
        data = {{}}
        for field, sel in SELECTORS.items():
            el = soup.select_one(sel)
            data[field] = el.get_text(strip=True) if el else None
        return data


def fetch_url(url: str) -> str:
    """Fetch page HTML. Retries on failure."""
    fetcher = Fetcher(auto_match=False)
    for attempt in range(3):
        try:
            resp = fetcher.get(url)
            if resp and resp.status == 200 and resp.body:
                return resp.body.decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  Retry {{attempt+1}}/3 for {{url}}: {{e}}", file=sys.stderr)
            time.sleep(2 ** attempt)
    return ""


def save_results(results, output_path: str = "output.json", fmt: str = "json"):
    """Save results to JSON or CSV."""
    if fmt == "csv":
        import csv
        if isinstance(results, dict):
            results = [results]
        if not results:
            print("No results to save.", file=sys.stderr)
            return
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 script.py <URL>")
        print("       python3 script.py urls.txt [--csv output.csv]")
        sys.exit(1)

    csv_output = None
    urls = []
    i = 0
    while i < len(args):
        if args[i] == "--csv" and i + 1 < len(args):
            csv_output = args[i + 1]
            i += 2
        else:
            urls.append(args[i])
            i += 1

    # Check if input is a file with URLs
    input_path = Path(urls[0]) if urls else None
    if input_path and input_path.is_file() and not str(input_path).startswith("http"):
        urls = [line.strip() for line in input_path.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")]

    all_results = []
    for idx, url in enumerate(urls):
        print(f"[{{idx+1}}/{{len(urls)}}] {{url}}")
        html = fetch_url(url)
        if not html:
            print(f"  FAILED to fetch {{url}}", file=sys.stderr)
            continue
        result = extract_from_html(html)
        if isinstance(result, list):
            all_results.extend(result)
            print(f"  Extracted {{len(result)}} items")
        else:
            all_results.append(result)
            print(f"  Extracted: {{result}}")

        if idx < len(urls) - 1 and True:  # delay between requests
            time.sleep(random.uniform(1.0, 3.0))

    # Save
    out_fmt = "csv" if csv_output else "json"
    out_path = csv_output or "output.json"
    save_results(all_results, out_path, out_fmt)
    print(f"\\nSaved {{len(all_results)}} results to {{out_path}} ({{out_fmt}})")


if __name__ == "__main__":
    main()
''')

        return script

    @staticmethod
    def save(script: str, path: str):
        """Save generated script to file."""
        p = Path(path)
        p.write_text(script, encoding="utf-8")
        p.chmod(0o755)
        log.info(f"Script saved to {p}")
