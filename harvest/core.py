"""Core — Page scraping and content extraction."""

import asyncio
import re
from datetime import datetime
from typing import Any, Optional

from .browser import BrowserSession
from .cache import ResponseCache
from .captcha_solver import CaptchaSolver
from .proxy_rotator import ProxyRotator
from .rate_limiter import RateLimiter
from .stealth import Stealth

# Optional AdaptiveCore integration
try:
    from adaptive.capture import record as capture_record

    HAVE_ADAPTIVE = True
except ImportError:
    HAVE_ADAPTIVE = False


class Scraper:
    """Extract structured content from any web page.

    Handles Cloudflare, Turnstile/hCaptcha, JS rendering, anti-bot protections.
    Reuses one browser session for all requests.
    """

    def __init__(
        self,
        proxy: Optional[str] = None,
        headless: bool = True,
        use_rotator: bool = True,
        use_stealth: bool = True,
        use_captcha_solver: bool = True,
        rate_limit: int = 10,
        domain_limits: Optional[dict[str, int]] = None,
        cache_ttl: int = 300,
        proxy_pool: Optional[list[str]] = None,
    ):
        self.proxy = proxy
        self.headless = headless
        self.use_rotator = use_rotator
        self.use_stealth = use_stealth
        self.use_captcha_solver = use_captcha_solver
        self._session: Optional[BrowserSession] = None
        self.rate_limiter = RateLimiter(
            max_per_minute=rate_limit,
            domain_limits=domain_limits,
        )
        self.cache = ResponseCache(ttl_seconds=cache_ttl)

        if use_rotator:
            self.proxy_rotator = ProxyRotator(pool=proxy_pool)
        if use_captcha_solver:
            self.captcha_solver = CaptchaSolver()
        if use_stealth:
            self.stealth = Stealth()

    async def _get_session(self, url: str = "") -> BrowserSession:
        """Get or create persistent browser session with domain-aware proxy."""
        if self._session is None:
            proxy = self.proxy
            if self.use_rotator and url:
                domain = ProxyRotator.get_domain(url)
                proxy = await self.proxy_rotator.get_for_domain(domain) or proxy

            additional_args = {}
            if self.use_stealth:
                additional_args.update(self.stealth.get_args())

            self._session = await BrowserSession.create(
                proxy=proxy,
                headless=self.headless,
                solve_cloudflare=True,
                additional_args=additional_args,
            )
        return self._session

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def scrape(
        self,
        url: str,
        selector: Optional[str] = None,
        extraction: str = "markdown",
    ) -> dict:
        try:
            cached = self.cache.get(url)
            if cached:
                return cached

            await self.rate_limiter.acquire(url)

            session = await self._get_session(url)

            if self.use_captcha_solver and hasattr(self, "captcha_solver"):
                try:
                    page = session.get_playwright_page()
                    await self.captcha_solver.solve(page, "#cf-turnstile, #hcaptcha-box")
                except Exception:
                    pass

            resp = await session.fetch(
                url,
                extraction_type=extraction,
                main_content_only=(selector is None),
                css_selector=selector,
            )

            content = ""
            title = ""
            if hasattr(resp, "body"):
                body = resp.body
                if isinstance(body, bytes):
                    content = body.decode("utf-8", errors="replace")
                elif isinstance(body, str):
                    content = body
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

            title_match = re.search(r"<title[^>]*>(.*?)</title>", content, re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()

            if HAVE_ADAPTIVE and content:
                try:
                    capture_record("scrape", f"OK {url[:60]}", True, tool="harvest")
                except Exception:
                    pass

            result = {
                "url": url,
                "title": title or url,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            }
            self.cache.set(url, result)
            return result
        except Exception as e:
            if HAVE_ADAPTIVE:
                try:
                    capture_record(
                        "scrape",
                        f"FAIL {url[:50]}: {str(e)[:80]}",
                        False,
                        tool="harvest",
                    )
                except Exception:
                    pass
            raise

    async def scrape_many(
        self,
        urls: list[str],
        selector: Optional[str] = None,
        extraction: str = "markdown",
    ) -> list[dict]:
        tasks = [self.scrape(url, selector, extraction) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                output.append(
                    {
                        "url": urls[i],
                        "error": str(r),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
            else:
                output.append(r)
        return output

    async def evaluate(self, url: str, js_expression: str) -> Any:
        """Scrape a URL and evaluate JS expression on the rendered page."""
        await self.rate_limiter.acquire(url)
        session = await self._get_session(url)
        await session.fetch(url, extraction_type="text")
        return await session.evaluate(js_expression)

    async def browse(self, url: str, page_action: callable) -> Any:
        async with BrowserSession(proxy=self.proxy, headless=self.headless) as session:
            return await session.fetch(url, page_action=page_action)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
