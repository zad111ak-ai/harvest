"""API Detector — Reverse-engineer hidden GraphQL/REST APIs from browser traffic.

Monitors network requests while browsing a page, identifies API endpoints,
classifies them (REST/GraphQL/WebSocket), extracts parameters and auth headers,
and generates ready-to-use httpx/requests code.

Features:
- Request/response interception via Playwright (patchright)
- GraphQL query extraction and parameter analysis
- Auth header detection (Bearer, API-Key, cookies)
- Rate limit detection from response headers
- Code generation (httpx, requests, curl)
- Replay without browser (10x faster, 0 tokens)

Usage:
    from harvest.api_detector import APIDetector

    detector = APIDetector()
    async with detector:
        await detector.visit("https://example.com", interact=True)
        apis = detector.get_apis()
        for api in apis:
            print(api)
            print(detector.generate_code(api))
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional
from urllib.parse import urlparse, parse_qs, urlencode

log = logging.getLogger("harvest.api_detector")


# ─── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class APIRequest:
    """Captured network request with metadata."""

    url: str
    method: str
    resource_type: str  # xhr, fetch, document, script, etc.
    headers: dict[str, str] = field(default_factory=dict)
    post_data: Optional[str] = None
    query_params: dict[str, str] = field(default_factory=dict)
    timestamp: float = 0.0

    # Filled after response
    status: int = 0
    response_headers: dict[str, str] = field(default_factory=dict)
    response_size: int = 0
    response_time_ms: float = 0.0
    tags: list = __import__("dataclasses").field(default_factory=list)

    # Classification
    api_type: str = "unknown"  # rest, graphql, websocket, sse, static
    auth_type: str = "none"  # none, bearer, api-key, cookie, basic
    auth_value: str = ""
    is_paginated: bool = False
    pagination_style: str = ""  # cursor, offset, page, link-header

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "method": self.method,
            "resource_type": self.resource_type,
            "api_type": self.api_type,
            "auth_type": self.auth_type,
            "query_params": self.query_params,
            "post_data": self.post_data[:500] if self.post_data else None,
            "status": self.status,
            "response_time_ms": self.response_time_ms,
            "response_size": self.response_size,
            "is_paginated": self.is_paginated,
        }


@dataclass
class APIEndpoint:
    """Aggregated API endpoint (grouped by path + method)."""

    path: str
    method: str
    api_type: str
    domain: str
    auth_type: str = "none"
    auth_value: str = ""
    sample_params: dict[str, str] = field(default_factory=dict)
    sample_body: Optional[str] = None
    response_example: Optional[str] = None
    response_schema: Optional[dict] = None
    headers: dict[str, str] = field(default_factory=dict)
    rate_limit: Optional[dict[str, Any]] = None
    is_paginated: bool = False
    pagination_style: str = ""
    call_count: int = 1
    avg_response_ms: float = 0.0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "method": self.method,
            "api_type": self.api_type,
            "domain": self.domain,
            "auth_type": self.auth_type,
            "sample_params": self.sample_params,
            "sample_body": self.sample_body[:500] if self.sample_body else None,
            "rate_limit": self.rate_limit,
            "is_paginated": self.is_paginated,
            "call_count": self.call_count,
            "avg_response_ms": self.avg_response_ms,
            "tags": self.tags,
        }


# ─── Classifier ───────────────────────────────────────────────────────────────


class RequestClassifier:
    """Classify network requests by type and extract metadata."""

    # Patterns for GraphQL
    _GRAPHQL_PATTERNS = [
        re.compile(r"/graphql", re.IGNORECASE),
        re.compile(r"/api/graphql", re.IGNORECASE),
        re.compile(r"/gql", re.IGNORECASE),
    ]

    # Auth header patterns
    _BEARER_RE = re.compile(r"Bearer\s+([A-Za-z0-9\-._~+/]+=*)", re.IGNORECASE)
    _API_KEY_HEADERS = {
        "x-api-key",
        "x-api-token",
        "authorization",
        "x-auth-token",
        "x-access-token",
        "api-key",
        "x-csrf-token",
    }

    # Pagination patterns
    _CURSOR_KEYS = {"cursor", "after", "before", "start_cursor", "end_cursor"}
    _OFFSET_KEYS = {"offset", "skip", "start", "page", "p"}
    _LINK_REL_RE = re.compile(r'<[^>]+>;\s*rel="next"', re.IGNORECASE)

    # Rate limit headers
    _RATE_LIMIT_HEADERS = {
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "retry-after",
        "x-rate-limit-limit",
        "x-rate-limit-remaining",
    }

    @classmethod
    def classify(
        cls,
        url: str,
        method: str,
        headers: dict,
        post_data: Optional[str],
        resource_type: str,
    ) -> APIRequest:
        """Classify a single request."""
        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        # Flatten single-value lists
        query_flat = {k: v[0] if len(v) == 1 else ",".join(v) for k, v in query.items()}

        req = APIRequest(
            url=url,
            method=method,
            resource_type=resource_type,
            headers={k.lower(): v for k, v in headers.items()},
            post_data=post_data,
            query_params=query_flat,
            timestamp=time.time(),
        )

        # Classify API type
        req.api_type = cls._detect_api_type(url, method, headers, post_data, resource_type)

        # Detect auth
        req.auth_type, req.auth_value = cls._detect_auth(headers)

        # Detect pagination
        req.is_paginated, req.pagination_style = cls._detect_pagination(query_flat, headers, post_data)

        return req

    @classmethod
    def _detect_api_type(
        cls,
        url: str,
        method: str,
        headers: dict,
        post_data: Optional[str],
        resource_type: str,
    ) -> str:
        # Skip static resources
        if resource_type in ("image", "stylesheet", "font", "media", "manifest"):
            return "static"

        # GraphQL detection
        for pat in cls._GRAPHQL_PATTERNS:
            if pat.search(url):
                return "graphql"

        # Check if POST body is GraphQL
        if post_data:
            try:
                body = json.loads(post_data)
                if "query" in body and ("operationName" in body or "variables" in body):
                    return "graphql"
            except (json.JSONDecodeError, TypeError):
                pass

        # WebSocket
        if url.startswith("ws://") or url.startswith("wss://"):
            return "websocket"

        # SSE (Server-Sent Events)
        accept = headers.get("accept", headers.get("Accept", ""))
        if "text/event-stream" in accept:
            return "sse"

        # REST API heuristic: XHR/fetch with JSON response
        if resource_type in ("xhr", "fetch"):
            content_type = headers.get("content-type", headers.get("Content-Type", ""))
            if "json" in content_type or "graphql" in content_type:
                return "rest"

            # URL pattern heuristics
            if re.search(r"/api/|/v\d+/|/rest/", url, re.IGNORECASE):
                return "rest"

        return "static"

    @classmethod
    def _detect_auth(cls, headers: dict) -> tuple[str, str]:
        for header_name in cls._API_KEY_HEADERS:
            value = headers.get(header_name, "")
            if not value:
                continue

            # Bearer token
            if header_name == "authorization":
                m = cls._BEARER_RE.search(value)
                if m:
                    return "bearer", m.group(1)[:20] + "..."
                return "basic", "***"

            # API key
            return "api-key", value[:15] + "..."

        return "none", ""

    @classmethod
    def _detect_pagination(cls, query: dict, headers: dict, post_data: Optional[str]) -> tuple[bool, str]:
        # Query param pagination
        if cls._CURSOR_KEYS & query.keys():
            return True, "cursor"
        if cls._OFFSET_KEYS & query.keys():
            return True, "offset"

        # Link header
        link = headers.get("link", headers.get("Link", ""))
        if cls._LINK_REL_RE.search(link):
            return True, "link-header"

        # Body pagination
        if post_data:
            try:
                body = json.loads(post_data)
                if cls._CURSOR_KEYS & body.keys():
                    return True, "cursor"
                if cls._OFFSET_KEYS & body.keys():
                    return True, "offset"
            except (json.JSONDecodeError, TypeError):
                pass

        return False, ""

    @classmethod
    def extract_rate_limit(cls, headers: dict) -> Optional[dict[str, Any]]:
        """Extract rate limit info from response headers."""
        rl = {}
        for h in cls._RATE_LIMIT_HEADERS:
            if h in headers:
                try:
                    rl[h] = int(headers[h])
                except (ValueError, TypeError):
                    rl[h] = headers[h]

        if rl:
            return rl
        return None


# ─── Code Generator ───────────────────────────────────────────────────────────


class CodeGenerator:
    """Generate executable code for discovered API endpoints."""

    @staticmethod
    def httpx(endpoint: APIEndpoint, response_example: Optional[str] = None) -> str:
        """Generate httpx async client code."""
        lines = [
            "import httpx",
            "",
            "async def fetch_data():",
            f'    """Call {endpoint.method} {endpoint.path}"""',
            f'    url = "https://{endpoint.domain}{endpoint.path}"',
        ]

        # Headers
        if endpoint.auth_type != "none" or endpoint.headers:
            lines.append("    headers = {")
            if endpoint.auth_type == "bearer":
                lines.append('        "Authorization": "Bearer YOUR_TOKEN",')
            elif endpoint.auth_type == "api-key":
                lines.append('        "x-api-key": "YOUR_API_KEY",')
            for k, v in endpoint.headers.items():
                if k.lower() not in ("authorization", "x-api-key", "cookie"):
                    lines.append(f'        "{k}": "{v[:50]}",')
            lines.append("    }")

        # Query params
        if endpoint.sample_params:
            params_json = json.dumps(endpoint.sample_params, indent=8)
            lines.append(f"    params = {params_json}")

        # Request
        req_args = ["url"]
        if endpoint.auth_type != "none" or endpoint.headers:
            req_args.append("headers=headers")
        if endpoint.sample_params:
            req_args.append("params=params")

        if endpoint.method == "POST" and endpoint.sample_body:
            lines.append(f"    payload = {endpoint.sample_body[:200]}")
            req_args.append("json=payload")

        req_str = ", ".join(req_args)
        lines.append("    async with httpx.AsyncClient() as client:")
        lines.append(f"        resp = await client.{endpoint.method.lower()}({req_str})")
        lines.append("        resp.raise_for_status()")
        lines.append("        return resp.json()")

        # Usage
        lines.extend(
            [
                "",
                "",
                "# Usage:",
                "# result = asyncio.run(fetch_data())",
            ]
        )

        return "\n".join(lines)

    @staticmethod
    def requests(endpoint: APIEndpoint) -> str:
        """Generate requests library code."""
        lines = [
            "import requests",
            "",
            "def fetch_data():",
            f'    """Call {endpoint.method} {endpoint.path}"""',
            f'    url = "https://{endpoint.domain}{endpoint.path}"',
        ]

        headers = {}
        if endpoint.auth_type == "bearer":
            headers["Authorization"] = "Bearer YOUR_TOKEN"
        elif endpoint.auth_type == "api-key":
            headers["x-api-key"] = "YOUR_API_KEY"

        if headers:
            lines.append(f"    headers = {json.dumps(headers, indent=8)}")

        if endpoint.sample_params:
            lines.append(f"    params = {json.dumps(endpoint.sample_params, indent=8)}")

        req_args = ["url"]
        if headers:
            req_args.append("headers=headers")
        if endpoint.sample_params:
            req_args.append("params=params")

        if endpoint.method == "POST" and endpoint.sample_body:
            lines.append(f"    payload = {endpoint.sample_body[:200]}")
            req_args.append("json=payload")

        req_str = ", ".join(req_args)
        lines.append(f"    resp = requests.{endpoint.method.lower()}({req_str})")
        lines.append("    resp.raise_for_status()")
        lines.append("    return resp.json()")

        return "\n".join(lines)

    @staticmethod
    def curl(endpoint: APIEndpoint) -> str:
        """Generate curl command."""
        parts = ["curl", "-s"]

        if endpoint.method != "GET":
            parts.append(f"-X {endpoint.method}")

        # Auth
        if endpoint.auth_type == "bearer":
            parts.append('-H "Authorization: Bearer YOUR_TOKEN"')
        elif endpoint.auth_type == "api-key":
            parts.append('-H "x-api-key: YOUR_API_KEY"')

        for k, v in endpoint.headers.items():
            if k.lower() not in ("authorization", "x-api-key", "cookie", "user-agent"):
                parts.append(f'-H "{k}: {v[:50]}"')

        if endpoint.method == "POST" and endpoint.sample_body:
            body = endpoint.sample_body[:200].replace('"', '\\"')
            parts.append(f"-d '{body}'")

        url = f"https://{endpoint.domain}{endpoint.path}"
        if endpoint.sample_params:
            qs = urlencode(endpoint.sample_params)
            url += f"?{qs}"

        parts.append(f'"{url}"')
        return " \\\n  ".join(parts)


# ─── Main Detector ────────────────────────────────────────────────────────────


class APIDetector:
    """Monitor browser traffic and extract hidden API endpoints.

    Usage:
        async with APIDetector() as detector:
            await detector.visit("https://example.com")
            apis = detector.get_apis()
    """

    def __init__(
        self,
        proxy: Optional[str] = None,
        headless: bool = True,
        timeout: int = 60000,
        filter_static: bool = True,
        max_requests: int = 500,
        auto_scroll: bool = True,
    ):
        self._proxy = proxy
        self._headless = headless
        self._timeout = timeout
        self._filter_static = filter_static
        self._max_requests = max_requests
        self._auto_scroll = auto_scroll

        self._session = None
        self._requests: list[APIRequest] = []
        self._endpoints: dict[str, APIEndpoint] = {}
        self._started = False
        self._visit_count = 0

    async def start(self):
        """Initialize Scrapling browser session."""
        if self._started:
            return

        from scrapling.fetchers import AsyncStealthySession

        kwargs: dict[str, Any] = {
            "headless": self._headless,
            "max_pages": 1,
            "timeout": self._timeout,
            "solve_cloudflare": True,
        }
        if self._proxy:
            kwargs["proxy"] = self._proxy

        self._session = AsyncStealthySession(**kwargs)  # type: ignore[arg-type]
        await self._session.start()
        self._started = True

    async def close(self):
        """Clean up browser session."""
        if self._started and self._session:
            await self._session.close()
            self._session = None
            self._started = False

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()

    def _setup_interception(self, page) -> list[APIRequest]:
        """Attach request/response listeners to a Playwright page."""
        captured: list[APIRequest] = []

        def on_request(req):
            if len(captured) >= self._max_requests:
                return
            try:
                headers = dict(req.headers) if hasattr(req, "headers") else {}
                post_data = req.post_data if hasattr(req, "post_data") else None
                rtype = req.resource_type if hasattr(req, "resource_type") else "xhr"

                api_req = RequestClassifier.classify(
                    url=req.url,
                    method=req.method,
                    headers=headers,
                    post_data=post_data,
                    resource_type=rtype,
                )
                api_req.timestamp = time.time() * 1000
                captured.append(api_req)
            except Exception as e:
                log.debug("Intercept error: %s", e)

        def on_response(resp):
            # Match response to captured request
            req_url = resp.url if hasattr(resp, "url") else ""
            for api_req in reversed(captured):
                if api_req.url == req_url and api_req.status == 0:
                    api_req.status = resp.status if hasattr(resp, "status") else 0
                    api_req.response_headers = dict(resp.headers) if hasattr(resp, "headers") else {}
                    # Detect rate limits
                    rl = RequestClassifier.extract_rate_limit(api_req.response_headers)
                    if rl:
                        api_req.tags = [f"rate_limit:{rl}"]
                    break

        page.on("request", on_request)
        page.on("response", on_response)
        return captured

    async def visit(
        self,
        url: str,
        interact: bool = False,
        scroll_count: int = 5,
        action: Optional[Callable] = None,
    ) -> list[APIRequest]:
        """Visit a URL and capture all API requests.

        Args:
            url: Page URL to visit
            interact: Auto-scroll and click common elements
            scroll_count: Number of scroll iterations
            action: Custom async action(page) for advanced interaction

        Returns:
            List of captured API requests
        """
        if not self._started:
            await self.start()

        ctx = self._session.context  # type: ignore[union-attr]
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        captured = self._setup_interception(page)

        log.info("Visiting %s", url)
        try:
            await page.goto(url, wait_until="networkidle", timeout=self._timeout)
        except Exception as e:
            log.warning("Navigation issue (partial load OK): %s", e)

        # Wait for dynamic content
        await asyncio.sleep(2)

        # Auto-scroll to trigger lazy-loaded APIs
        if self._auto_scroll and interact:
            for i in range(scroll_count):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(1.5)

        # Click common "load more" buttons
        if interact:
            for selector in [
                'button:has-text("Load More")',
                'button:has-text("Show More")',
                'a:has-text("Next")',
                '[data-testid="pagination-next"]',
                ".load-more",
                ".show-more",
            ]:
                try:
                    btn = await page.query_selector(selector)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(2)
                except Exception:
                    pass

        # Custom action
        if action:
            try:
                await action(page)
                await asyncio.sleep(1)
            except Exception as e:
                log.warning("Custom action error: %s", e)

        # Merge into master list
        self._requests.extend(captured)
        self._visit_count += 1

        log.info(
            "Captured %d requests (%d API), total: %d",
            len(captured),
            sum(1 for r in captured if r.api_type != "static"),
            len(self._requests),
        )
        return captured

    def get_apis(self, deduplicate: bool = True) -> list[APIEndpoint]:
        """Get discovered API endpoints, optionally deduplicated.

        Returns:
            List of APIEndpoint objects with aggregated info
        """
        if not deduplicate:
            return [self._req_to_endpoint(r) for r in self._requests if r.api_type != "static"]

        endpoints: dict[str, APIEndpoint] = {}

        for req in self._requests:
            if req.api_type == "static":
                continue

            parsed = urlparse(req.url)
            key = f"{req.method}:{parsed.path}"

            if key in endpoints:
                ep = endpoints[key]
                ep.call_count += 1
                ep.avg_response_ms = (ep.avg_response_ms * (ep.call_count - 1) + req.response_time_ms) / ep.call_count
                # Update auth if newly discovered
                if ep.auth_type == "none" and req.auth_type != "none":
                    ep.auth_type = req.auth_type
                    ep.auth_value = req.auth_value
                # Update params
                for k, v in req.query_params.items():
                    if k not in ep.sample_params:
                        ep.sample_params[k] = v
            else:
                endpoints[key] = self._req_to_endpoint(req)

        self._endpoints = endpoints
        return list(endpoints.values())

    def _req_to_endpoint(self, req: APIRequest) -> APIEndpoint:
        """Convert a single request to an endpoint."""
        parsed = urlparse(req.url)
        return APIEndpoint(
            path=parsed.path,
            method=req.method,
            api_type=req.api_type,
            domain=parsed.netloc,
            auth_type=req.auth_type,
            auth_value=req.auth_value,
            sample_params=dict(req.query_params),
            sample_body=req.post_data[:500] if req.post_data else None,
            headers={
                k: v for k, v in req.headers.items() if k.lower() not in ("user-agent", "accept-encoding", "accept")
            },
            is_paginated=req.is_paginated,
            pagination_style=req.pagination_style,
            avg_response_ms=req.response_time_ms,
        )

    def generate_code(self, endpoint: APIEndpoint, style: str = "httpx") -> str:
        """Generate executable code for an API endpoint.

        Args:
            endpoint: APIEndpoint to generate code for
            style: 'httpx', 'requests', or 'curl'

        Returns:
            Generated code string
        """
        if style == "httpx":
            return CodeGenerator.httpx(endpoint)
        elif style == "requests":
            return CodeGenerator.requests(endpoint)
        elif style == "curl":
            return CodeGenerator.curl(endpoint)
        else:
            raise ValueError(f"Unknown style: {style}. Use 'httpx', 'requests', or 'curl'")

    def export(self, path: Optional[str] = None) -> dict:
        """Export all discovered APIs as a dict (for JSON save).

        Args:
            path: Optional file path to save JSON

        Returns:
            Dict with metadata and endpoints
        """
        endpoints = self.get_apis()
        data = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_requests": len(self._requests),
            "total_endpoints": len(endpoints),
            "endpoints": [ep.to_dict() for ep in endpoints],
        }

        if path:
            with open(path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            log.info("Exported %d endpoints to %s", len(endpoints), path)

        return data

    def summary(self) -> str:
        """Human-readable summary of discovered APIs."""
        endpoints = self.get_apis()
        total = len(self._requests)
        api_count = sum(1 for r in self._requests if r.api_type != "static")

        lines = [
            "🔍 API Discovery Report",
            f"   Total requests: {total}",
            f"   API requests: {api_count}",
            f"   Unique endpoints: {len(endpoints)}",
            "",
        ]

        # Group by type
        by_type: dict[str, list[APIEndpoint]] = {}
        for ep in endpoints:
            by_type.setdefault(ep.api_type, []).append(ep)

        for api_type, eps in sorted(by_type.items()):
            lines.append(f"📋 {api_type.upper()} ({len(eps)})")
            for ep in eps:
                auth = f" 🔐{ep.auth_type}" if ep.auth_type != "none" else ""
                pag = f" 📄{ep.pagination_style}" if ep.is_paginated else ""
                calls = f" ×{ep.call_count}" if ep.call_count > 1 else ""
                lines.append(f"   {ep.method:6s} {ep.path}{auth}{pag}{calls}")
            lines.append("")

        return "\n".join(lines)

    @property
    def request_count(self) -> int:
        return len(self._requests)

    @property
    def api_count(self) -> int:
        return sum(1 for r in self._requests if r.api_type != "static")
