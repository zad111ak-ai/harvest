"""
BrowserSession — Reusable Scrapling browser session with Cloudflare bypass.

One browser, many pages. Proxy support. Human-like behavior.
"""

import asyncio
from typing import Optional, Callable, Any, Dict

try:
    from scrapling.fetchers import AsyncStealthySession
except ImportError:
    AsyncStealthySession = None  # type: ignore[assignment,misc]


class BrowserSession:
    async def evaluate(self, expression: str, **kwargs) -> Any:
        """Execute JavaScript in the page context and return the result.

        Args:
            expression: JavaScript expression to evaluate

        Returns:
            The result of the JavaScript expression
        """
        if not self._started:
            await self.start()

        # Get the Playwright page from the session
        page = self.get_playwright_page()
        if page is None:
            raise RuntimeError("No active page in browser session")

        return await page.evaluate(expression, **kwargs)

    async def extract_structured(self, js_expression: str, **kwargs) -> list[dict]:
        """Execute JS that returns an array of objects (e.g. product listings).

        The JS expression must return an array of plain objects.
        Each object becomes a dict in the result list.

        Args:
            js_expression: JS expression returning Array<Object>

        Returns:
            List of dicts from JS evaluation
        """
        result = await self.evaluate(js_expression, **kwargs)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [result]
        return [{"value": result}]

    """Reusable browser session via Scrapling AsyncStealthySession.

    Features:
    - One browser process, many pages (parallel fetch via max_pages)
    - Cloudflare Turnstile/Interstitial bypass
    - HTTP proxy support
    - Human-like fingerprinting

    Usage:
        async with BrowserSession() as session:
            resp = await session.fetch("https://example.com")
    """

    def __init__(
        self,
        proxy: Optional[str] = None,
        headless: bool = True,
        timeout: int = 60000,
        solve_cloudflare: bool = True,
        load_dom: bool = True,
        network_idle: bool = False,
        max_pages: int = 3,
        additional_args: Optional[Dict[str, Any]] = None,
    ):
        if AsyncStealthySession is None:
            raise ImportError("scrapling is not installed. Install it with: pip install scrapling")

        # Filter out invalid args for AsyncStealthySession
        valid_args = {
            "max_pages": max_pages,
            "headless": headless,
            "proxy": proxy,
            "timeout": timeout,
            "solve_cloudflare": solve_cloudflare,
            "load_dom": load_dom,
            "network_idle": network_idle,
        }

        # Merge additional_args if provided
        if additional_args:
            valid_args.update(additional_args)

        self._session = AsyncStealthySession(**valid_args)  # type: ignore[arg-type]
        self._started = False

    @classmethod
    async def create(cls, **kwargs) -> "BrowserSession":
        self = cls(**kwargs)
        await self.start()
        return self

    async def start(self):
        await self._session.start()
        self._started = True

    async def fetch(
        self,
        url: str,
        page_action: Optional[Callable] = None,
        page_setup: Optional[Callable] = None,
        extraction_type: str = "markdown",
        **kwargs,
    ) -> Any:
        """Fetch a URL and return the page content or page_action result."""
        if not self._started:
            await self.start()
        return await self._session.fetch(
            url,
            page_action=page_action,
            page_setup=page_setup,
            extraction_type=extraction_type,
            **kwargs,
        )  # type: ignore[call-arg]

    async def close(self):
        if self._started:
            await self._session.close()
            self._started = False

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()

    def get_playwright_page(self):
        """Get the underlying Playwright Page object for custom actions."""
        return self._session._browser_context.pages[0]


# ============ HTML HELPERS ============


def extract_keys_from_html(html: str, patterns: list[str]) -> list[str]:
    """Extract values from HTML by regex patterns."""
    import re

    found = set()
    keys = []
    for pat in patterns:
        for m in re.finditer(pat, html):
            val = m.group(0)
            if val not in found:
                found.add(val)
                keys.append(val)
    return keys


def find_verify_link(body: str) -> Optional[str]:
    """Extract verification/confirmation link from email body."""
    import re

    urls = re.findall(r'https?://[^\s"\'<>\[\]]+', body)
    for u in urls:
        u_lower = u.lower()
        if any(x in u_lower for x in ["verify", "confirm", "activate", "callback", "magic"]):
            return u
    return None


# ============ COMMON PAGE ACTIONS ============


async def click_submit_button(page, selector: str = 'button[type="submit"]'):
    btn = await page.query_selector(selector)
    if btn:
        await btn.click()
        await asyncio.sleep(2)


async def fill_field(page, selector: str, value: str):
    el = await page.query_selector(selector)
    if el:
        await el.fill(value)
        await asyncio.sleep(0.5)


async def wait_and_get_html(page, timeout: int = 5000) -> str:
    try:
        await page.wait_for_load_state("load", timeout=timeout)
    except Exception:
        pass
    await asyncio.sleep(1)
    return await page.content()
