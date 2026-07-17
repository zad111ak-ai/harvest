"""
Server — FastAPI HTTP API server for Harvest.

Like ScrapingBee / Browse AI API — send a URL, get structured data.
Self-hosted, free, unlimited.

Usage:
    harvest serve
    curl http://localhost:8590/scrape?url=https://example.com
    curl -X POST http://localhost:8590/extract \\
        -H "Content-Type: application/json" \\
        -d '{"url": "https://shop.com", "schema": {"price": ".price", "title": "h1"}}'
"""

import time
from typing import Optional

from . import __version__
from .core import Scraper
from .extract import SchemaExtractor
from .crawl import SiteCrawler
from .contacts import ContactCollector
from .config import Config
from .mcp_tools import add_mcp_tools


def create_app(config: Optional[Config] = None):
    """Create FastAPI application with all endpoints.

    Usage:
        from harvest.server import create_app
        app = create_app()
        # uvicorn.run(app, host="127.0.0.1", port=8590)

    Or via CLI:
        harvest serve
    """
    from fastapi import FastAPI, Query, HTTPException
    from fastapi.responses import JSONResponse
    from fastapi.requests import Request
    from pydantic import BaseModel
    import os
    import hmac as _hmac

    cfg = config or Config()

    app = FastAPI(
        title="Harvest API",
        description="Universal web collection engine — scrape, extract, crawl, monitor any website through Cloudflare",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # SECURITY: Optional bearer token auth (set HARVEST_API_TOKEN env var)
    _api_token = os.environ.get("HARVEST_API_TOKEN", "")

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        # Skip auth for health check and docs
        if request.url.path in (
            "/health",
            "/stats",
            "/docs",
            "/redoc",
            "/openapi.json",
        ):
            return await call_next(request)

        # If no token configured, allow all (backward compat)
        if not _api_token:
            return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided = auth_header[7:]
        else:
            provided = ""

        if not provided or not _hmac.compare_digest(provided, _api_token):
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or missing API token. Set HARVEST_API_TOKEN."},
            )

        return await call_next(request)

    # SECURITY: Log auth status
    if _api_token:
        print("🔒 Harvest API: Auth ENABLED (HARVEST_API_TOKEN set)")
    else:
        print("⚠️  Harvest API: Auth DISABLED (set HARVEST_API_TOKEN for production)")

    # Add MCP tools
    add_mcp_tools(app)

    # ── Request models ──

    class ScrapeRequest(BaseModel):
        url: str
        selector: Optional[str] = None
        output: str = "json"

    class ExtractRequest(BaseModel):
        url: str
        schema: dict  # type: ignore[assignment]

    class CrawlRequest(BaseModel):
        url: str
        max_pages: int = 50
        delay: float = 0.5
        sitemap_only: bool = False

    class ContactsRequest(BaseModel):
        url: str
        depth: int = 2

    class BatchRequest(BaseModel):
        requests: list[ScrapeRequest]

    # ── Rate limiter ──
    rate_limit = cfg.get("server", "rate_limit", default=60)
    _request_times: list[float] = []

    # ── Endpoints ──

    @app.get("/")
    async def root():
        return {
            "service": "Harvest API",
            "version": __version__,
            "endpoints": {
                "GET /scrape": "Scrape a URL",
                "POST /extract": "Extract structured data",
                "POST /crawl": "Crawl a website",
                "GET /contacts": "Find contacts on a website",
                "POST /batch": "Batch scrape multiple URLs",
                "GET /health": "Health check",
            },
            "docs": "/docs",
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": __version__, "timestamp": time.time()}

    @app.get("/scrape")
    async def scrape(
        url: str = Query(..., description="URL to scrape"),
        selector: Optional[str] = Query(None, description="CSS selector"),
        output: str = Query("json", description="Output format: json, md, txt"),
        proxy: Optional[str] = Query(None),
        headless: bool = Query(True),
    ):
        _check_rate_limit()
        scraper = Scraper(proxy=proxy or cfg.get("proxy", "url") or None, headless=headless)
        try:
            result = await scraper.scrape(url, selector=selector)
            return result
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

    @app.post("/extract")
    async def extract(request: ExtractRequest):
        _check_rate_limit()
        extractor = SchemaExtractor()
        try:
            result = await extractor.extract(request.url, request.schema)
            return result
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

    @app.post("/crawl")
    async def crawl(request: CrawlRequest):
        _check_rate_limit()
        crawler = SiteCrawler(headless=True, delay=request.delay)
        result = await crawler.crawl(
            request.url,
            max_pages=request.max_pages,
            sitemap_only=request.sitemap_only,
        )
        return {
            "url": request.url,
            "total_pages": result["total_pages"],
            "pages": result.get("pages", []),
        }

    @app.get("/contacts")
    async def contacts(
        url: str = Query(...),
        depth: int = Query(2),
    ):
        _check_rate_limit()
        collector = ContactCollector()
        result = await collector.collect(url, depth=depth)
        return result

    @app.post("/batch")
    async def batch(request: BatchRequest):
        """Scrape multiple URLs in parallel."""
        scraper = Scraper()
        urls = [r.url for r in request.requests]
        import asyncio

        tasks = [scraper.scrape(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                output.append({"url": urls[i], "error": str(r)})
            else:
                output.append(r)  # type: ignore[arg-type]

        return {"results": output, "total": len(output)}

    # ── Middleware ──

    def _check_rate_limit():
        now = time.time()
        global _request_times
        # Remove requests older than 60s
        _request_times = [t for t in _request_times if now - t < 60]
        if len(_request_times) >= rate_limit:
            raise HTTPException(status_code=429, detail=f"Rate limit: {rate_limit} req/min")
        _request_times.append(now)

    return app


def run_server(config: Optional[Config] = None, host: str = "127.0.0.1", port: int = 8590):
    """Run the Harvest API server."""
    import uvicorn

    cfg = config or Config()
    host = cfg.get("server", "host", default=host)
    port = cfg.get("server", "port", default=port)
    workers = cfg.get("server", "workers", default=1)
    rate_limit = cfg.get("server", "rate_limit", default=60)

    print(f"\n🌾 Harvest API v{__version__}")
    print(f"   Listening on http://{host}:{port}")
    print(f"   Rate limit: {rate_limit} req/min")
    print(f"   Workers: {workers}")
    print(f"   Docs: http://{host}:{port}/docs")
    print(f"   Redoc: http://{host}:{port}/redoc\n")

    uvicorn.run(
        "harvest.server:create_app",
        host=host,
        port=port,
        workers=workers,
        factory=True,
        log_level="info",
    )
