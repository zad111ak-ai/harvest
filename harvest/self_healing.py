"""Self-Healing Parsers — Auto-regenerate CSS selectors when sites change.

When a website updates its layout, CSS selectors break. This module detects
breakage and uses LLM to regenerate working selectors automatically.

Usage:
    parser = SelfHealingParser(url="https://shop.com")
    result = await parser.extract(
        html=new_html,
        schema={"price": ".price-value", "title": "h1"},
    )
    # If selectors broke → auto-regenerates via LLM → returns data
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup

log = logging.getLogger("harvest.self_healing")


def _hash_html(html: str) -> str:
    return hashlib.md5(html.encode("utf-8", errors="replace")).hexdigest()[:12]


def _test_selectors(html: str, selectors: dict[str, str]) -> dict[str, bool]:
    """Test which selectors still work on the given HTML.

    Returns: {field_name: found_any_match}
    """
    soup = BeautifulSoup(html, "html.parser")
    results = {}
    for field, css in selectors.items():
        try:
            found = soup.select(css)
            results[field] = len(found) > 0
        except Exception:
            results[field] = False
    return results


def _extract_with_selectors(html: str, selectors: dict[str, str]) -> dict[str, Any]:
    """Extract data using CSS selectors."""
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, Any] = {}
    for field, css in selectors.items():
        try:
            elements = soup.select(css)
            if elements:
                texts = [el.get_text(strip=True) for el in elements]
                result[field] = texts[0] if len(texts) == 1 else texts
            else:
                result[field] = None
        except Exception:
            result[field] = None
    return result


def _build_regeneration_prompt(
    old_html_sample: str,
    new_html_sample: str,
    old_selectors: dict[str, str],
    schema: Optional[dict] = None,
) -> str:
    """Build an LLM prompt to regenerate broken selectors."""
    schema_desc = ""
    if schema:
        schema_desc = f"\nTarget schema: {json.dumps(schema, indent=2)}"

    return f"""A website changed its HTML structure and CSS selectors broke.

OLD HTML (structural sample):
{old_html_sample[:3000]}

NEW HTML (structural sample):
{new_html_sample[:3000]}

Broken CSS selectors:
{json.dumps(old_selectors, indent=2)}
{schema_desc}

Generate NEW CSS selectors that extract the same data from the NEW HTML.
Return ONLY a JSON object mapping field names to new CSS selectors.
Example: {{"price": ".new-price-class", "title": "h1.product-title"}}

JSON:"""


class SelfHealingParser:
    """Auto-regenerate CSS selectors when websites change their layout.

    Stores HTML+selector history per URL. On extraction, tests existing
    selectors first. If broken, regenerates via LLM and validates.
    """

    def __init__(
        self,
        url: str = "",
        data_dir: Optional[str] = None,
        llm_base_url: str = "http://localhost:3000/v1",
        llm_model: str = "auto/best-chat",
        llm_api_key: str = "sk-omniroute",
    ):
        self.url = url
        self.data_dir = Path(data_dir or "~/.harvest/self_healing").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.llm_base_url = llm_base_url
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        self.history: list[dict] = []

    def _history_path(self) -> Path:
        url_hash = hashlib.md5(self.url.encode()).hexdigest()[:12]
        return self.data_dir / f"{url_hash}.json"

    def load_history(self):
        """Load selector history from disk."""
        path = self._history_path()
        if path.exists():
            with open(path) as f:
                self.history = json.load(f)

    def save_history(self):
        """Save selector history to disk."""
        path = self._history_path()
        with open(path, "w") as f:
            json.dump(self.history, f, indent=2)

    async def extract(
        self,
        html: str,
        schema: dict[str, str],
        selector_field: str = "css",
    ) -> dict:
        """Extract data with auto-healing selectors.

        Args:
            html: Current page HTML.
            schema: {field_name: css_selector} mapping.
            selector_field: Key in schema that holds CSS selectors.

        Returns:
            dict with: data, healed (bool), old_selectors, new_selectors, details
        """
        self.load_history()

        # Find last known good selectors
        last_entry = None
        for entry in reversed(self.history):
            if entry.get("schema") == schema:
                last_entry = entry
                break

        if last_entry:
            old_selectors = last_entry["selectors"]
        else:
            old_selectors = schema

        # Test current selectors
        test_results = _test_selectors(html, old_selectors)
        all_work = all(test_results.values())

        if all_work:
            data = _extract_with_selectors(html, old_selectors)
            return {
                "data": data,
                "healed": False,
                "selectors": old_selectors,
                "details": f"All {len(old_selectors)} selectors working",
            }

        # Some selectors broken → attempt healing
        broken = [f for f, ok in test_results.items() if not ok]
        log.info(f"Self-healing: {len(broken)} broken selectors for {self.url}")

        # Build old HTML sample from history
        old_html_sample = ""
        if last_entry:
            old_html_sample = last_entry.get("html_sample", "")

        new_selectors = await self._regenerate_via_llm(old_html_sample, html, old_selectors, schema)

        if new_selectors:
            # Validate new selectors
            new_test = _test_selectors(html, new_selectors)
            still_broken = [f for f, ok in new_test.items() if not ok]

            if len(still_broken) < len(broken):
                # Improvement! Use new selectors
                data = _extract_with_selectors(html, new_selectors)

                # Save to history
                self.history.append(
                    {
                        "html_sample": html[:5000],
                        "selectors": new_selectors,
                        "schema": schema,
                        "html_hash": _hash_html(html),
                    }
                )
                # Keep last 10 entries
                self.history = self.history[-10:]
                self.save_history()

                return {
                    "data": data,
                    "healed": True,
                    "old_selectors": old_selectors,
                    "new_selectors": new_selectors,
                    "broken_fixed": len(broken) - len(still_broken),
                    "still_broken": still_broken,
                    "details": f"Fixed {len(broken) - len(still_broken)}/{len(broken)} selectors",
                }

        # Healing failed → fall back to original schema
        return {
            "data": _extract_with_selectors(html, schema),
            "healed": False,
            "old_selectors": old_selectors,
            "new_selectors": None,
            "broken": broken,
            "details": f"Auto-healing failed for: {', '.join(broken)}",
        }

    async def _regenerate_via_llm(
        self,
        old_html: str,
        new_html: str,
        old_selectors: dict[str, str],
        schema: Optional[dict],
    ) -> Optional[dict[str, str]]:
        """Call LLM to regenerate broken selectors."""
        try:
            import aiohttp

            prompt = _build_regeneration_prompt(old_html, new_html, old_selectors, schema)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.llm_base_url}/chat/completions",
                    json={
                        "model": self.llm_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                        "max_tokens": 1000,
                    },
                    headers={
                        "Authorization": f"Bearer {self.llm_api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]

                    # Parse JSON from response
                    # Try to extract JSON from markdown code block
                    json_match = content.split("```json")[-1].split("```")[0].strip()
                    if not json_match:
                        json_match = content.strip()

                    new_selectors = json.loads(json_match)
                    if isinstance(new_selectors, dict) and all(isinstance(v, str) for v in new_selectors.values()):
                        return new_selectors

        except Exception as e:
            log.warning(f"LLM regeneration failed: {e}")

        return None
