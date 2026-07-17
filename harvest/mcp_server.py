"""Harvest MCP Server — stdio transport for Claude Desktop, Cursor, Windsurf.

Usage:
    harvest-mcp                    # stdio mode (for Claude Desktop / Cursor)
    harvest-mcp --transport sse    # SSE mode (for remote access)

Claude Desktop config (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "harvest": {
          "command": "harvest-mcp",
          "args": []
        }
      }
    }
"""

import asyncio
import json
import logging
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

# Suppress noisy logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

server = Server("harvest")

# ─── Tool definitions ──────────────────────────────────────────────────────

TOOLS = [
    Tool(
        name="harvest_scrape",
        description="Scrape a web page and return its content as clean Markdown. Handles Cloudflare, anti-bot, JavaScript rendering.",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to scrape",
                },
                "selector": {
                    "type": "string",
                    "description": "Optional CSS selector to extract specific content (e.g. 'div.product')",
                },
                "extraction": {
                    "type": "string",
                    "enum": ["markdown", "text", "html"],
                    "description": "Output format (default: markdown)",
                    "default": "markdown",
                },
            },
            "required": ["url"],
        },
    ),
    Tool(
        name="harvest_extract",
        description="Extract structured data from a web page using LLM. Describe what you want in natural language — no CSS selectors needed.",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to extract from",
                },
                "prompt": {
                    "type": "string",
                    "description": "What to extract in natural language, e.g. 'Extract product name, price, and rating'",
                },
                "schema": {
                    "type": "object",
                    "description": "Optional JSON schema for structured output",
                },
            },
            "required": ["url", "prompt"],
        },
    ),
    Tool(
        name="harvest_crawl",
        description="Crawl a website and extract data from multiple pages following links.",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Starting URL to crawl",
                },
                "max_pages": {
                    "type": "integer",
                    "description": "Maximum number of pages to crawl (default: 10)",
                    "default": 10,
                },
                "selector": {
                    "type": "string",
                    "description": "Optional CSS selector to extract from each page",
                },
            },
            "required": ["url"],
        },
    ),
    Tool(
        name="harvest_contacts",
        description="Extract contact information (emails, phones, social links) from a web page.",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to extract contacts from",
                },
            },
            "required": ["url"],
        },
    ),
    Tool(
        name="harvest_batch",
        description="Scrape multiple URLs in parallel and return results for each.",
        inputSchema={
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of URLs to scrape",
                },
                "selector": {
                    "type": "string",
                    "description": "Optional CSS selector to apply to all URLs",
                },
            },
            "required": ["urls"],
        },
    ),
]


# ─── Handlers ───────────────────────────────────────────────────────────────


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    try:
        if name == "harvest_scrape":
            result = await _scrape(
                url=arguments["url"],
                selector=arguments.get("selector"),
                extraction=arguments.get("extraction", "markdown"),
            )
        elif name == "harvest_extract":
            result = await _extract(
                url=arguments["url"],
                prompt=arguments["prompt"],
                schema=arguments.get("schema"),
            )
        elif name == "harvest_crawl":
            result = await _crawl(
                url=arguments["url"],
                max_pages=arguments.get("max_pages", 10),
                selector=arguments.get("selector"),
            )
        elif name == "harvest_contacts":
            result = await _contacts(url=arguments["url"])
        elif name == "harvest_batch":
            result = await _batch(
                urls=arguments["urls"],
                selector=arguments.get("selector"),
            )
        elif name.startswith("denseforge_") and _DENSEFORGE_AVAILABLE:
            result = await _denseforge_call(name, arguments)
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                isError=True,
            )

        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))],
        )

    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {type(e).__name__}: {e}")],
            isError=True,
        )


# ─── Implementation ────────────────────────────────────────────────────────


async def _scrape(url: str, selector: Optional[str] = None, extraction: str = "markdown") -> dict:
    """Scrape a single URL."""
    from harvest.core import Scraper

    scraper = Scraper(use_stealth=True)
    result = await scraper.scrape(url, selector=selector, extraction=extraction)
    return result


async def _extract(url: str, prompt: str, schema: Optional[dict] = None) -> dict:
    """Extract structured data using LLM."""
    from harvest.extract import LLMExtractor

    extractor = LLMExtractor()
    result = await extractor.extract(url=url, description=prompt, schema=schema)
    return result


async def _crawl(url: str, max_pages: int = 10, selector: Optional[str] = None) -> dict:
    """Crawl a website following links."""
    from harvest.crawl import SiteCrawler

    crawler = SiteCrawler(max_pages=max_pages)
    results = await crawler.crawl([url])
    return {"pages_crawled": len(results), "results": results}


async def _contacts(url: str) -> dict:
    """Extract contact info from a page."""
    from harvest.contacts import ContactCollector

    extractor = ContactCollector()
    result = await extractor.collect(url)
    return result


async def _batch(urls: list[str], selector: Optional[str] = None) -> list[dict]:
    """Scrape multiple URLs in parallel."""
    from harvest.core import Scraper

    scraper = Scraper(use_stealth=True)
    tasks = [scraper.scrape(url, selector=selector) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for url, result in zip(urls, results):
        if isinstance(result, Exception):
            output.append({"url": url, "error": str(result)})
        elif isinstance(result, dict):
            output.append({"url": url, **result})
        else:
            output.append({"url": url, "data": str(result)})
    return output


# ─── DenseForge integration (optional) ──────────────────────────────────────

_DENSEFORGE_AVAILABLE = False
try:
    from harvest.integrations.denseforge import DenseForgeBridge

    _bridge = DenseForgeBridge()
    _DENSEFORGE_AVAILABLE = _bridge.available
except Exception:
    _bridge = None

if _DENSEFORGE_AVAILABLE:
    TOOLS.extend(
        [
            Tool(
                name="denseforge_search",
                description="Search DenseForge knowledge base (semantic search over ingested documents)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "top_k": {
                            "type": "integer",
                            "description": "Max results (default: 5)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="denseforge_ingest",
                description="Ingest a web page into DenseForge knowledge base for future retrieval",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Source URL"},
                        "content": {
                            "type": "string",
                            "description": "Text content to ingest",
                        },
                        "title": {
                            "type": "string",
                            "description": "Document title (optional)",
                        },
                    },
                    "required": ["url", "content"],
                },
            ),
            Tool(
                name="denseforge_ask_why",
                description="Causal reasoning: why did this happen? (requires DenseForge knowledge)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "effect": {
                            "type": "string",
                            "description": "The effect to explain",
                        },
                    },
                    "required": ["effect"],
                },
            ),
            Tool(
                name="denseforge_stats",
                description="Get DenseForge knowledge base statistics",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]
    )


async def _denseforge_call(name: str, args: dict):
    """Route DenseForge tool calls."""
    if not _DENSEFORGE_AVAILABLE or not _bridge:
        return {"error": "DenseForge not installed"}

    try:
        if name == "denseforge_search":
            result = await _bridge.search(args["query"], top_k=args.get("top_k", 5))
        elif name == "denseforge_ingest":
            result = await _bridge.ingest(args["url"], args["content"], {"title": args.get("title", "")})
            result = {"ingested": result} if isinstance(result, list) else result
        elif name == "denseforge_ask_why":
            result = await _bridge.ask_why(args["effect"])
        elif name == "denseforge_stats":
            result = await _bridge.stats()
        else:
            return {"error": f"Unknown DenseForge tool: {name}"}

        return result if result is not None else {"error": "No result from DenseForge"}
    except Exception as e:
        return {"error": str(e)}


# ─── Entry point ────────────────────────────────────────────────────────────


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def cli():
    """CLI entry point for harvest-mcp."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()
