"""
MCP Tools for Harvest v0.5.0 — Proxy, Captcha, Stealth, Scheduler.

Usage:
    hermes mcp add harvest --command 'harvest-mcp'
"""

from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel


def add_mcp_tools(app: FastAPI) -> None:
    """Add new MCP tools to Harvest server."""

    class ProxyRequest(BaseModel):
        url: str
        use_rotator: bool = True
        use_stealth: bool = True

    class ScheduleRequest(BaseModel):
        url: str
        cron: str
        selector: Optional[str] = None

    @app.post("/proxy_scrape")
    async def proxy_scrape(request: ProxyRequest):
        from harvest.core import Scraper

        scraper = Scraper(
            use_rotator=request.use_rotator,
            use_stealth=request.use_stealth,
        )
        result = await scraper.scrape(request.url)
        return result

    @app.post("/schedule")
    async def schedule(request: ScheduleRequest):
        from harvest.scheduler import Scheduler

        scheduler = Scheduler()
        job_id = scheduler.schedule(
            url=request.url,
            cron=request.cron,
            selector=request.selector,
        )
        return {"job_id": job_id, "status": "scheduled"}

    @app.get("/proxy_list")
    async def proxy_list():
        from harvest.proxy_rotator import ProxyRotator

        rotator = ProxyRotator()
        await rotator.load_proxies()
        await rotator.refresh_healthy()
        return {
            "total_proxies": len(rotator.proxies),
            "healthy_proxies": len(rotator.healthy_proxies),
            "proxies": rotator.healthy_proxies,
        }
