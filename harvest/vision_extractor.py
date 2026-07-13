"""Vision-based extraction using screenshots + LLM vision APIs.

Extracts data from screenshots of web pages using multimodal LLMs.
Works with GPT-4 Vision, Claude 3.5 Sonnet, and other vision-capable models.

Usage:
    from harvest.vision_extractor import VisionExtractor

    extractor = VisionExtractor()
    result = await extractor.extract(
        url="https://shop.com",
        prompt="Find all product prices"
    )
"""

import asyncio
import base64
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


class VisionExtractor:
    """Extract data from web page screenshots using vision-capable LLMs."""

    def __init__(
        self,
        base_url: str = "http://localhost:3000/v1",
        model: str = "auto/best-chat",
        api_key: str = "sk-placeholder",
        timeout: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self._screenshot_dir: Optional[Path] = None

    async def extract(
        self,
        url: str,
        prompt: str,
        screenshot_path: Optional[str] = None,
        context: Optional[str] = None,
    ) -> dict[str, Any]:
        """Extract data from a web page using vision.

        Args:
            url: URL of the page to extract from
            prompt: Natural language description of what to extract
            screenshot_path: Optional pre-existing screenshot path
            context: Optional additional context about the page

        Returns:
            Dict with 'extracted', 'confidence', 'method' keys
        """
        # 1. Take screenshot if not provided
        img_path: Optional[str] = None
        if screenshot_path and Path(screenshot_path).exists():
            img_path = screenshot_path
        else:
            img_path = await self._take_screenshot(url)

        if not img_path:
            return {
                "url": url,
                "extracted": None,
                "error": "Failed to take screenshot",
                "method": "vision",
            }

        # 2. Encode screenshot to base64
        img_b64 = self._encode_image(img_path)
        if not img_b64:
            return {
                "url": url,
                "extracted": None,
                "error": "Failed to encode screenshot",
                "method": "vision",
            }

        # 3. Build prompt with context
        system_prompt = self._build_system_prompt(context)
        user_prompt = self._build_user_prompt(url, prompt)

        # 4. Send to vision LLM
        result = await self._call_vision_api(
            img_b64=img_b64,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # 5. Parse response
        if result.get("error"):
            return {
                "url": url,
                "extracted": None,
                "error": result["error"],
                "method": "vision",
            }

        extracted = self._parse_llm_response(result.get("content", ""))

        return {
            "url": url,
            "extracted": extracted,
            "confidence": result.get("confidence", 0.8),
            "method": "vision",
            "model": self.model,
            "screenshot": str(img_path),
        }

    async def extract_from_html(
        self,
        url: str,
        html: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Extract data from HTML by first rendering to screenshot.

        Useful for hybrid mode: HTML + Vision fallback.
        """
        # Save HTML to temp file and take screenshot
        with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False) as f:
            f.write(html)
            html_path = f.name

        try:
            # Try to take screenshot of the HTML file
            img_path = await self._take_screenshot(f"file://{html_path}")
            if img_path:
                return await self.extract(
                    url=url,
                    prompt=prompt,
                    screenshot_path=img_path,
                    context="Extracted from rendered HTML",
                )
        finally:
            Path(html_path).unlink(missing_ok=True)

        return {
            "url": url,
            "extracted": None,
            "error": "Failed to render HTML to screenshot",
            "method": "vision",
        }

    async def _take_screenshot(self, url: str) -> Optional[str]:
        """Take a screenshot of a URL using Scrapling's browser."""
        try:
            from .browser import BrowserSession

            # Create temp file for screenshot
            screenshot_dir = Path(tempfile.mkdtemp(prefix="harvest_vision_"))
            screenshot_path = screenshot_dir / "screenshot.png"

            async with BrowserSession(headless=True) as session:
                # Fetch the page
                await session.fetch(url, extraction_type="html")

                # Use Scrapling's get_playwright_page() to access Playwright
                try:
                    page = session.get_playwright_page()
                    if page:
                        await page.screenshot(path=str(screenshot_path), full_page=True)
                        logger.info(f"Screenshot saved: {screenshot_path}")
                        return str(screenshot_path)
                except (AttributeError, IndexError, RuntimeError) as e:
                    logger.warning(f"Could not access Playwright page: {e}")

            logger.warning("Could not access Playwright page for screenshot")
            return None

        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    def _encode_image(self, image_path: str) -> Optional[str]:
        """Encode image to base64."""
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode image: {e}")
            return None

    def _build_system_prompt(self, context: Optional[str] = None) -> str:
        """Build system prompt for vision LLM."""
        base = """You are a data extraction assistant. You analyze screenshots of web pages and extract structured data.

Rules:
1. Return valid JSON only
2. Extract data exactly as shown (preserve numbers, dates, text)
3. If data is not visible, return null for that field
4. Be precise with prices, dates, and measurements
5. Handle multiple items by returning arrays"""

        if context:
            base += f"\n\nContext: {context}"

        return base

    def _build_user_prompt(self, url: str, prompt: str) -> str:
        """Build user prompt with image reference."""
        return f"""URL: {url}

Task: {prompt}

Analyze this screenshot and extract the requested data. Return JSON with the extracted fields."""

    async def _call_vision_api(
        self,
        img_b64: str,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        """Call vision LLM API with image."""
        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            "max_tokens": 4096,
            "temperature": 0.0,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        return {"error": f"API error {resp.status}: {text}"}

                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return {"content": content}

        except asyncio.TimeoutError:
            return {"error": f"Vision API timeout ({self.timeout}s)"}
        except Exception as e:
            return {"error": f"Vision API error: {str(e)}"}

    def _parse_llm_response(self, content: str) -> Any:
        """Parse LLM response, extracting JSON."""
        # Try to find JSON in response
        content = content.strip()

        # Handle markdown code blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end != -1:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end != -1:
                content = content[start:end].strip()

        # Try parsing as JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object or array
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start = content.find(start_char)
            end = content.rfind(end_char)
            if start != -1 and end > start:
                try:
                    return json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    continue

        # Return raw text if no JSON found
        return {"raw_response": content}
