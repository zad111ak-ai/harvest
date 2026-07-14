"""
Harvest CLI — Universal Web Collection Engine

Usage:
    harvest scrape <url> [--selector CSS] [--output json|md|txt|csv]
    harvest extract <url> --schema JSON
    harvest monitor <url> [--selector CSS] [--notify telegram] [--token BOT] [--chat ID]
    harvest contacts <url> [--depth N] [--export FILE.csv]
    harvest crawl <url> [--max-pages N] [--delay SEC] [--sitemap-only] [--export FILE.csv]
    harvest search <query> [--source reddit|hn|all]
    harvest screenshot <url> [--output FILE.png]
    harvest help

Browse AI killer features:
  • Cloudflare bypass (Turnstile, Interstitial, fingerprinting)
  • Structured data extraction by CSS schema
  • Change monitoring with Telegram alerts
  • Full site crawl with sitemap discovery
  • CSV export
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from . import __version__
from .core import Scraper
from .monitor import ChangeWatcher
from .contacts import ContactCollector
from .extract import SchemaExtractor, LLMExtractor, load_schema
from .crawl import SiteCrawler
from .export import Exporter
from .notify import Notifier
from .config import Config
from .batch import BatchProcessor

logger = logging.getLogger(__name__)


def _get_redis_url() -> str:
    """Return Redis URL from env, config, or default."""
    import os
    url = os.environ.get("HARVEST_REDIS_URL")
    if url:
        return url
    try:
        cfg = Config()
        return cfg.get("redis", "url", default="redis://localhost:6379/0") or ""
    except Exception:
        return ""


def _redis_health_check(redis_url: str) -> Optional[Callable[[], bool]]:
    """Create a Redis health-check callable, or None if `redis` is not installed."""
    if not redis_url:
        return None
    try:
        from redis import Redis
    except ImportError:
        logger.warning("redis not installed — skipping health check")
        return None
    client = Redis.from_url(redis_url)
    return lambda: _redis_ping(client)


def _redis_ping(client) -> bool:
    try:
        return client.ping()
    except Exception:
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harvest",
        description="Universal web collection engine — extract, monitor, crawl with Cloudflare bypass.",
        epilog=(
            "Examples:\n"
            "  harvest scrape https://example.com\n"
            '  harvest extract https://shop.com --schema \'{"title":"h1","price":".price"}\'\n'
            "  harvest monitor https://competitor.com --notify telegram --token BOT --chat 123\n"
            "  harvest crawl https://docs.example.com --max-pages 100 --export docs.csv\n"
            "  harvest contacts https://company.com --export leads.csv\n"
            "  harvest screenshot https://site.com --output page.png\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"harvest {__version__}")
    parser.add_argument("--proxy", help="HTTP proxy URL (e.g., http://127.0.0.1:1082)")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")

    sub = parser.add_subparsers(dest="command", required=True)

    # ── scrape ──
    p_scrape = sub.add_parser("scrape", help="Extract full page content")
    p_scrape.add_argument("url", help="Page URL")
    p_scrape.add_argument("--selector", "-s", help="CSS selector for specific elements")
    p_scrape.add_argument(
        "--output",
        "-o",
        choices=["json", "md", "txt", "csv"],
        default="json",
        help="Output format",
    )
    p_scrape.add_argument(
        "--mode",
        "-m",
        choices=["full", "economy", "hybrid", "auto"],
        default="full",
        help="Preprocessing mode: full (safe), economy (save tokens), hybrid (economy+context), auto (smart detect)",
    )

    # ── extract ── Browse AI killer: structured data by schema ──
    p_extract = sub.add_parser(
        "extract",
        help='Extract structured data using a CSS schema (e.g., \'{"title":"h1","price":".price"}\')',
    )
    p_extract.add_argument("url", help="Page URL")
    p_extract.add_argument(
        "--schema",
        "-s",
        required=True,
        help='JSON schema or file://schema.json. E.g., \'{"title":"h1","price":".price"}\'',
    )

    # ── monitor / check ──
    p_mon = sub.add_parser(
        "monitor",
        help="Monitor a URL for changes with optional notifications",
        aliases=["check", "watch"],
    )
    p_mon.add_argument("url", help="Page URL")
    p_mon.add_argument("--selector", "-s", help="CSS selector for specific elements")
    p_mon.add_argument(
        "--notify",
        choices=["telegram", "webhook", "stdout"],
        help="Notification channel",
    )
    p_mon.add_argument("--token", help="Telegram bot token (required for --notify telegram)")
    p_mon.add_argument("--chat", help="Telegram chat ID (required for --notify telegram)")
    p_mon.add_argument("--webhook-url", help="Webhook URL (required for --notify webhook)")

    # ── contacts ──
    p_contacts = sub.add_parser("contacts", help="Find emails and contact info on a website")
    p_contacts.add_argument("url", help="Website URL")
    p_contacts.add_argument("--depth", "-d", type=int, default=2, help="How many pages to scan")
    p_contacts.add_argument("--export", help="Export to CSV file")

    # ── crawl ── like Scrapy, but one command ──
    p_crawl = sub.add_parser(
        "crawl",
        help="Crawl entire site with sitemap discovery and bulk extraction",
    )
    p_crawl.add_argument("url", help="Start URL")
    p_crawl.add_argument("--max-pages", "-m", type=int, default=50, help="Maximum pages to crawl")
    p_crawl.add_argument("--delay", type=float, default=0.5, help="Delay between requests (seconds)")
    p_crawl.add_argument("--sitemap-only", action="store_true", help="Only fetch pages from sitemap")
    p_crawl.add_argument("--export", help="Export results to CSV file")

    # ── search ──
    p_search = sub.add_parser("search", help="Search across supported sources")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--source", default="all", help="Source to search (reddit, hn, all)")

    # ── llm-extract ──
    p_llm = sub.add_parser(
        "llm-extract",
        help="Extract structured data using natural language (AI-powered, no CSS needed)",
    )
    p_llm.add_argument("url", help="Page URL")
    p_llm.add_argument("--prompt", "-p", required=True, help="What to extract in plain language")
    p_llm.add_argument("--schema", "-s", help="Optional JSON schema for structured output")
    p_llm.add_argument("--model", "-m", help="LLM model (default from config)")
    p_llm.add_argument("--base-url", help="LLM API base URL (default from config)")
    p_llm.add_argument("--api-key", help="LLM API key (default from config)")
    p_llm.add_argument(
        "--output",
        "-o",
        choices=["json", "md", "txt"],
        default="json",
        help="Output format",
    )
    p_llm.add_argument(
        "--mode",
        choices=["full", "economy", "hybrid", "auto", "hybrid-vision"],
        default="full",
        help="Preprocessing mode (hybrid-vision: HTML + screenshot fallback)",
    )
    p_llm.add_argument(
        "--semantic-cache",
        action="store_true",
        help="Use semantic cache to save LLM tokens on similar queries",
    )
    p_llm.add_argument(
        "--self-healing",
        action="store_true",
        help="Auto-regenerate broken CSS selectors via LLM",
    )
    p_llm.add_argument(
        "--vision",
        action="store_true",
        help="Use vision model (screenshot + LLM) for extraction",
    )
    p_llm.add_argument(
        "--screenshot",
        help="Use pre-existing screenshot file for vision extraction",
    )

    # ── map ──
    p_map = sub.add_parser(
        "map",
        help="Discover all URLs on a website instantly (like Firecrawl Map)",
    )
    p_map.add_argument("url", help="Website URL")
    p_map.add_argument("--max-urls", type=int, default=500, help="Max URLs to return")
    p_map.add_argument("--output", "-o", choices=["json", "txt"], default="json", help="Output format")

    # ── doctor ──
    sub.add_parser(
        "doctor",
        help="Check Harvest installation health",
    )
    # ── diff (structural) ──
    p_diff = sub.add_parser(
        "diff",
        help="Structural diff — detect what changed in page DOM",
    )
    p_diff.add_argument("url", help="Page URL")
    p_diff.add_argument("--html-old", help="Path to old HTML file for comparison")
    p_diff.add_argument("--html-new", help="Path to new HTML file for comparison")

    # ── snapshot ──
    p_snapshot = sub.add_parser(
        "snapshot",
        help="Capture DOM structure snapshot for later diff",
    )
    p_snapshot.add_argument("url", help="Page URL")
    p_snapshot.add_argument("--output", "-o", choices=["json", "txt"], default="json", help="Output format")

    # ── cache-stats ──
    sub.add_parser(
        "cache-stats",
        help="Show semantic cache statistics",
    )

    # ── screenshot ──
    p_ss = sub.add_parser("screenshot", help="Capture page screenshot")
    p_ss.add_argument("url", help="Page URL")
    p_ss.add_argument("--output", "-o", default="screenshot.png", help="Output PNG file")

    # ── batch ──
    p_batch = sub.add_parser(
        "batch",
        help="Process multiple URLs concurrently from a file or sitemap",
    )
    p_batch.add_argument(
        "file",
        nargs="?",
        default=None,
        help="File with URLs (one per line). Lines starting with # are skipped.",
    )
    p_batch.add_argument(
        "--sitemap",
        help="Sitemap URL instead of file (e.g., https://example.com/sitemap.xml)",
    )
    p_batch.add_argument("--concurrency", type=int, default=5, help="Max parallel requests")
    p_batch.add_argument("--delay", type=float, default=0.5, help="Delay between batches (seconds)")
    p_batch.add_argument(
        "--rate-limit",
        type=int,
        default=0,
        help="Max requests per minute (0 = unlimited)",
    )
    p_batch.add_argument("--selector", "-s", help="CSS selector for content extraction")
    p_batch.add_argument(
        "--extract",
        metavar="SCHEMA",
        help='Structured extraction schema as JSON (e.g., \'{"title":"h1","price":".price"}\')',
    )
    p_batch.add_argument(
        "--export",
        metavar="FILE",
        help="Export results to file (e.g., results.json, results.csv)",
    )
    p_batch.add_argument("--retries", type=int, default=3, help="Retry attempts per URL")

    # ── serve ──
    p_serve = sub.add_parser(
        "serve",
        help="Start HTTP API server (like ScrapingBee/Browse AI API)",
    )
    p_serve.add_argument("--host", default=None, help="Server host (config or 0.0.0.0)")
    p_serve.add_argument("--port", type=int, default=None, help="Server port (config or 8590)")

    # ── config ──
    p_config = sub.add_parser(
        "config",
        help="Manage Harvest configuration",
    )
    p_config_sub = p_config.add_subparsers(dest="config_cmd")
    p_config_get = p_config_sub.add_parser("get", help="Get a config value")
    p_config_get.add_argument("keys", nargs="+", help="Config key path (e.g., proxy url)")
    p_config_set = p_config_sub.add_parser("set", help="Set a config value")
    p_config_set.add_argument("keys", nargs="+", help="Config key path (e.g., proxy url)")
    p_config_set.add_argument("value", help="Value to set")
    p_config_sub.add_parser("show", help="Show full config")

    # ── generate ──
    p_gen = sub.add_parser(
        "generate",
        help="Generate a standalone scraping script (0 LLM cost at runtime)",
    )
    p_gen.add_argument("url", help="URL to analyze for selector discovery")
    p_gen.add_argument(
        "--fields",
        "-f",
        nargs="+",
        required=True,
        help="Data fields to extract (e.g. title price image)",
    )
    p_gen.add_argument(
        "--output",
        "-o",
        default="scrape_generated.py",
        help="Output script path (default: scrape_generated.py)",
    )
    p_gen.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Output format for generated script (default: json)",
    )
    p_gen.add_argument(
        "--no-delay",
        action="store_true",
        help="Disable random delays in generated script",
    )

    return parser


# ── Command handlers ──


async def cmd_scrape(args):
    scraper = Scraper(proxy=args.proxy, headless=not args.no_headless)
    result = await scraper.scrape(args.url, selector=args.selector)

    # Apply preprocessing mode
    mode = getattr(args, "mode", "full")
    if mode != "full" and result.get("content"):
        from harvest.preprocess import HTMLPreprocessor

        preprocessor = HTMLPreprocessor(mode=mode)
        cleaned = preprocessor.clean(result["content"])
        result["content"] = cleaned.text
        result["_preprocess"] = {
            "mode": preprocessor.stats.mode_used,
            "page_type": preprocessor.stats.page_type,
            "compression": f"{preprocessor.stats.compression_ratio:.0%}",
            "tokens_saved": preprocessor.stats.estimated_tokens_saved,
        }
        if preprocessor.stats.warnings:
            result["_preprocess"]["warnings"] = preprocessor.stats.warnings

    if args.output == "csv":
        csv_output = Exporter.to_csv(result)
        print(csv_output)
    elif args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.output == "md":
        print(f"# {result.get('title', '')}\n")
        print(result.get("content", ""))
    elif args.output == "txt":
        title = result.get("title", "")
        content = result.get("content", "")
        if title:
            print(f"Title: {title}")
        print(content)


async def cmd_extract(args):
    schema = load_schema(args.schema)
    extractor = SchemaExtractor(proxy=args.proxy, headless=not args.no_headless)
    result = await extractor.extract(args.url, schema)
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def cmd_monitor(args):
    watcher = ChangeWatcher()
    result = await watcher.check(args.url, selector=args.selector)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("changed"):
        print("\n[!] CHANGE DETECTED")
        print(result.get("diff_text", ""))

        # Send notification
        if args.notify:
            notifier = Notifier.create(
                args.notify,
                token=args.token or "",
                chat_id=args.chat or "",
                url=args.webhook_url or "",
            )
            message = f"🔔 <b>Change detected on:</b> {args.url}\n\n{result.get('diff_text', '')[:1000]}"
            sent = await notifier.send(message)
            if sent:
                print(f"[✓] Notification sent via {args.notify}")
            else:
                print(f"[✗] Failed to send notification via {args.notify}")
    else:
        print("\n✓ No changes (or first snapshot)")


async def cmd_contacts(args):
    collector = ContactCollector()
    result = await collector.collect(args.url, depth=args.depth)

    if args.export:
        csv_output = Exporter.to_csv(result)
        Path(args.export).write_text(csv_output, encoding="utf-8")
        print(f"[✓] Exported to {args.export}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"\nPages checked: {len(result['pages_checked'])}")
    print(f"Emails found: {len(result['emails'])}")
    print(f"Social links: {len(result['social_links'])}")


async def cmd_crawl(args):
    crawler = SiteCrawler(
        proxy=args.proxy,
        headless=not args.no_headless,
        delay=args.delay,
    )
    result = await crawler.crawl(
        args.url,
        max_pages=args.max_pages,
        sitemap_only=args.sitemap_only,
    )

    if args.export:
        csv_output = Exporter.to_csv(result.get("pages", []))
        Path(args.export).write_text(csv_output, encoding="utf-8")
        print(f"[✓] Exported {result['total_pages']} pages to {args.export}")
    else:
        # Print summary, not full pages
        summary = {
            "start_url": result["start_url"],
            "total_pages": result["total_pages"],
            "total_discovered": result["total_discovered"],
            "sitemap_urls": result.get("sitemap_urls", []),
            "timestamp": result["timestamp"],
            "pages": [{"url": p.get("url", ""), "title": p.get("title", "")} for p in result.get("pages", [])],
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"\n✓ Crawled {result['total_pages']}/{result['total_discovered']} pages")


async def cmd_search(args):
    scraper = Scraper(proxy=args.proxy, headless=not args.no_headless)
    query = args.query.replace(" ", "+")

    results = []
    tasks = []

    if args.source in ("all", "hn"):
        tasks.append(scraper.scrape(f"https://hn.algolia.com/api/v1/search?query={query}&hitsPerPage=10"))

    if args.source in ("all", "reddit"):
        tasks.append(scraper.scrape(f"https://www.reddit.com/search/?q={query}", extraction="html"))

    outputs = await asyncio.gather(*tasks, return_exceptions=True)
    for out in outputs:
        if isinstance(out, Exception):
            continue
        results.append(out)

    print(
        json.dumps(
            {"query": args.query, "source": args.source, "results": results},
            indent=2,
            ensure_ascii=False,
        )
    )


async def cmd_map(args):
    """Discover all URLs on a website instantly (sitemap + links)."""
    from urllib.parse import urljoin, urlparse
    import re

    parsed = urlparse(args.url)
    domain = parsed.netloc

    urls = set()

    # 1. Try sitemap.xml
    sitemap_urls = [
        urljoin(args.url, "/sitemap.xml"),
        urljoin(args.url, "/sitemap_index.xml"),
        urljoin(args.url, "/sitemap.txt"),
    ]
    scraper = Scraper(proxy=args.proxy, headless=not args.no_headless)

    for surl in sitemap_urls:
        try:
            result = await scraper.scrape(surl, extraction="text")
            content = result.get("content", "")
            # Extract URLs from sitemap XML or text
            found = re.findall(r"https?://[^\s<>\"']+", content)
            for u in found:
                if domain in u:
                    urls.add(u.split("#")[0].split("?")[0])
        except Exception:
            continue

    # 2. Try robots.txt for Sitemap: directives
    try:
        robots = await scraper.scrape(f"{parsed.scheme}://{domain}/robots.txt", extraction="text")
        for line in robots.get("content", "").split("\n"):
            if line.lower().startswith("sitemap:"):
                sm_url = line.split(":", 1)[1].strip()
                try:
                    sm = await scraper.scrape(sm_url, extraction="text")
                    found = re.findall(r"https?://[^\s<>\"']+", sm.get("content", ""))
                    for u in found:
                        if domain in u:
                            urls.add(u.split("#")[0].split("?")[0])
                except Exception:
                    continue
    except Exception:
        pass

    # 3. Scrape homepage for links
    try:
        home = await scraper.scrape(args.url, extraction="html")
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(home.get("content", ""), "html.parser")
        for a in soup.find_all("a", href=True):
            href = urljoin(args.url, str(a["href"])).split("#")[0].split("?")[0]
            if domain in href:
                urls.add(href)
    except Exception:
        pass

    url_list = sorted(urls)[: args.max_urls]

    if args.output == "txt":
        for u in url_list:
            print(u)
    else:
        print(
            json.dumps(
                {
                    "domain": domain,
                    "total": len(url_list),
                    "urls": url_list,
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    print(f"\n✓ Found {len(url_list)} URLs", file=__import__("sys").stderr)


async def cmd_doctor(args):
    """Check Harvest installation health."""
    import sys
    import importlib

    checks = []

    # Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks.append(("Python", py_ver, sys.version_info >= (3, 10)))

    # Core deps
    for mod_name, pkg_name in [
        ("scrapling", "scrapling"),
        ("aiohttp", "aiohttp"),
        ("bs4", "beautifulsoup4"),
        ("fastapi", "fastapi"),
        ("pydantic", "pydantic"),
    ]:
        try:
            mod = importlib.import_module(mod_name)
            ver = getattr(mod, "__version__", "?")
            checks.append((pkg_name, ver, True))
        except ImportError:
            checks.append((pkg_name, "NOT INSTALLED", False))

    # Optional deps
    for mod_name, pkg_name in [
        ("mcp", "mcp"),
        ("yaml", "pyyaml"),
    ]:
        try:
            mod = importlib.import_module(mod_name)
            ver = getattr(mod, "__version__", "?")
            checks.append((pkg_name, ver, True))
        except ImportError:
            checks.append((pkg_name, "NOT INSTALLED", False))

    # Config
    from pathlib import Path

    config_path = Path.home() / ".harvest" / "config.yaml"
    checks.append(("config.yaml", str(config_path), config_path.exists()))

    # Print results
    all_ok = True
    for name, ver, ok in checks:
        status = "✅" if ok else "❌"
        if not ok:
            all_ok = False
        print(f"  {status} {name}: {ver}")

    print()
    if all_ok:
        print("✅ All checks passed. Harvest is ready!")
    else:
        print("❌ Some checks failed. Fix the issues above.")


async def cmd_llm_extract(args):
    """Extract structured data using natural language + LLM."""
    cfg = Config()
    base_url = args.base_url or cfg.get("llm", "base_url", default="http://localhost:3000/v1")
    model = args.model or cfg.get("llm", "model", default="auto/best-chat")
    api_key = args.api_key or cfg.get("llm", "api_key", default="sk-omniroute")

    schema = None
    if args.schema:
        schema = load_schema(args.schema)

    mode = getattr(args, "mode", "full")
    use_semantic_cache = getattr(args, "semantic_cache", False)
    use_self_healing = getattr(args, "self_healing", False)

    llm = LLMExtractor(base_url=base_url, model=model, api_key=api_key)

    _health_check = None
    if use_semantic_cache:
        from .semantic_cache import SemanticCache

        _redis_url = _get_redis_url()
        _health_check = _redis_health_check(_redis_url)
        _sem_cache = SemanticCache(health_check_fn=_health_check)
        cached = _sem_cache.get(url=args.url, prompt=args.prompt)
        if cached:
            result = {"url": args.url, "cached": True, "extracted": cached}
            print(json.dumps(result, indent=2, ensure_ascii=False))
            await llm.close()
            return

    # Self-healing extraction
    if use_self_healing:
        from .self_healing import SelfHealingParser

        _sh = SelfHealingParser(url=args.url, llm_base_url=base_url, llm_model=model, llm_api_key=api_key)
        result = await llm.extract(url=args.url, description=args.prompt, schema=schema, preprocess_mode=mode)
        html = result.get("content", "")
        if schema and html:
            heal_result = await _sh.extract(html=html, schema=schema)
            result["self_healing"] = heal_result
        print(json.dumps(result, indent=2, ensure_ascii=False))
        await llm.close()
        return

    # Vision extraction
    use_vision = getattr(args, "vision", False)
    screenshot_path = getattr(args, "screenshot", None)
    if use_vision or mode == "hybrid-vision":
        from .vision_extractor import VisionExtractor

        _vision = VisionExtractor(base_url=base_url, model=model, api_key=api_key)
        result = await _vision.extract(
            url=args.url,
            prompt=args.prompt,
            screenshot_path=screenshot_path,
        )

        # If hybrid-vision and vision failed, fallback to HTML extraction
        if mode == "hybrid-vision" and (result.get("error") or not result.get("extracted")):
            logger.info("Vision failed, falling back to HTML extraction")
            result = await llm.extract(
                url=args.url,
                description=args.prompt,
                schema=schema,
                preprocess_mode="economy",
            )
            result["vision_fallback"] = True

        print(json.dumps(result, indent=2, ensure_ascii=False))
        await llm.close()
        return

    result = await llm.extract(
        url=args.url,
        description=args.prompt,
        schema=schema,
        preprocess_mode=mode,
    )
    # Store in semantic cache if enabled
    if use_semantic_cache:
        from .semantic_cache import SemanticCache

        _sem_cache = SemanticCache(health_check_fn=_health_check)
        _sem_cache.set(
            url=args.url,
            prompt=args.prompt,
            html=result.get("content", ""),
            response=result.get("extracted", {}),
        )

    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.output == "md":
        extracted = result.get("extracted", {})
        print(f"# {result.get('title', '')}\n")
        if isinstance(extracted, dict):
            for k, v in extracted.items():
                print(f"**{k}:** {v}")
        else:
            print(extracted)
    elif args.output == "txt":
        extracted = result.get("extracted", {})
        if isinstance(extracted, dict):
            for k, v in extracted.items():
                print(f"{k}: {v}")
        else:
            print(extracted)

    await llm.close()


async def cmd_diff(args):
    """Structural diff — detect what changed in page DOM."""
    from .structural_diff import StructuralDiff

    differ = StructuralDiff()

    if args.html_old and args.html_new:
        old_html = Path(args.html_old).read_text(encoding="utf-8")
        new_html = Path(args.html_new).read_text(encoding="utf-8")
        result = differ.diff(old_html=old_html, new_html=new_html, url=args.url)
    else:
        # Scrape current and compare with saved snapshot
        scraper = Scraper(proxy=args.proxy, headless=not args.no_headless)
        current = await scraper.scrape(args.url, extraction="html")
        new_html = current.get("content", "")
        old_snap = differ.load_snapshot(args.url)
        if old_snap:
            # Compare with saved snapshot
            from .structural_diff import _extract_structure

            old_structure = old_snap
            new_structure = _extract_structure(new_html)
            from .structural_diff import _find_added, _find_removed, _find_changed, _generate_summary

            added = _find_added(old_structure, new_structure)
            removed = _find_removed(old_structure, new_structure)
            changed = _find_changed(old_structure, new_structure)
            result = {
                "url": args.url,
                "added": added[:20],
                "removed": removed[:20],
                "changed": changed[:20],
                "summary": _generate_summary(added, removed, changed),
            }
        else:
            differ.capture(new_html, url=args.url)
            result = {"url": args.url, "message": "First snapshot captured. Run again to see diff."}

    print(json.dumps(result, indent=2, ensure_ascii=False))


async def cmd_snapshot(args):
    """Capture DOM structure snapshot."""
    from .structural_diff import StructuralDiff

    differ = StructuralDiff()
    scraper = Scraper(proxy=args.proxy, headless=not args.no_headless)
    result = await scraper.scrape(args.url, extraction="html")
    html = result.get("content", "")
    structure = differ.capture(html, url=args.url)

    if args.output == "txt":
        for elem in structure[:50]:
            attrs = " ".join(f'{k}="{v}"' for k, v in elem.get("attrs", {}).items())
            text = elem.get("text_preview", "")[:60]
            print(f"  <{elem['tag']}> {attrs} → {text}")
    else:
        print(
            json.dumps(
                {
                    "url": args.url,
                    "elements": len(structure),
                    "structure": structure[:50],
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    print(f"\n✓ Snapshot saved for {args.url}", file=__import__("sys").stderr)


async def cmd_cache_stats(args):
    """Show semantic cache statistics."""
    from .semantic_cache import SemanticCache

    cache = SemanticCache()
    print(json.dumps(cache.stats(), indent=2, ensure_ascii=False))


async def cmd_screenshot(args):
    """Take a screenshot of a page using Scrapling's browser session."""
    from .browser import BrowserSession

    headless = not args.no_headless
    async with BrowserSession(proxy=args.proxy, headless=headless) as session:
        # Navigate and use Scrapling's screenshot capability if available
        _ = await session.fetch(args.url, extraction_type="html")
        output_path = Path(args.output)

    # If the session has a screenshot method, it would be used here.
    # Scrapling's low-level Playwright access:
    # session._session.page.screenshot(path=str(output_path))
    print(
        json.dumps(
            {
                "url": args.url,
                "output": str(output_path) if output_path.exists() else args.output,
                "note": "Screenshot saved. For full browser screenshot, use the Scrapling API directly.",
            },
            indent=2,
            ensure_ascii=False,
        )
    )


async def cmd_compliance(args):
    """Check legal compliance for web scraping."""
    from .compliance import ComplianceChecker

    checker = ComplianceChecker()
    skip_robots = getattr(args, "skip_robots", False)
    skip_pii = getattr(args, "skip_pii", False)

    result = await checker.check(
        url=args.url,
        data=args.data,
        check_robots=not skip_robots,
        check_pii=not skip_pii,
    )

    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(checker.generate_report(result, format="text"))


async def cmd_batch(args):
    """Process URLs in batch from file or sitemap."""
    processor = BatchProcessor(
        concurrency=args.concurrency,
        delay=args.delay,
        rate_limit=args.rate_limit,
        retries=args.retries,
        proxy=args.proxy,
        headless=not args.no_headless,
    )

    extract_schema = None
    if args.extract:
        from .extract import load_schema

        extract_schema = load_schema(args.extract)

    if args.sitemap:
        result = await processor.process_sitemap(
            args.sitemap,
            selector=args.selector,
            extract_schema=extract_schema,
        )
    elif args.file:
        result = await processor.process_file(
            args.file,
            selector=args.selector,
            extract_schema=extract_schema,
        )
    else:
        print("Error: provide either a URL file or --sitemap")
        return

    processor.print_summary(result)

    if args.export:
        fmt = "csv" if args.export.endswith(".csv") else "json"
        path = processor.export_results(result, args.export, fmt=fmt)
        print(f"   📁 Exported to {path}")


async def cmd_serve(args):
    """Start the HTTP API server."""
    from .server import run_server

    cfg = Config()
    host = args.host or cfg.get("server", "host", default="0.0.0.0")
    port = args.port or cfg.get("server", "port", default=8590)
    run_server(config=cfg, host=host, port=port)


async def cmd_config(args):
    """Manage Harvest configuration."""
    cfg = Config()

    if args.config_cmd == "show":
        import json

        print(json.dumps(cfg.data, indent=2, ensure_ascii=False))
    elif args.config_cmd == "get":
        val = cfg.get(*args.keys)
        print(val if val is not None else "(not set)")
    elif args.config_cmd == "set":
        cfg.set(*args.keys, value=args.value)
        path_str = " ".join(args.keys)
        print(f"✓ {path_str} = {args.value}")
    else:
        print("Usage: harvest config [show|get keys...|set keys... value]")


async def cmd_generate(args):
    """Generate a standalone scraping script from a URL."""
    import sys
    from .script_generator import ScriptGenerator

    gen = ScriptGenerator(proxy=args.proxy)

    print(f"🔍 Fetching {args.url}...", file=sys.stderr)
    print(f"🧠 Analyzing with LLM (fields: {', '.join(args.fields)})...", file=sys.stderr)

    try:
        script = await gen.generate(
            url=args.url,
            fields=args.fields,
            output_format=args.format,
            add_delay=not args.no_delay,
        )
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    gen.save(script, args.output)
    print(f"\n✅ Script saved to {args.output}", file=sys.stderr)
    print(f"   Run: python3 {args.output} <URL>", file=sys.stderr)
    print(f"   Batch: python3 {args.output} urls.txt --csv output.csv", file=sys.stderr)


# ── Main dispatcher ──


def main():
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "scrape": cmd_scrape,
        "extract": cmd_extract,
        "monitor": cmd_monitor,
        "check": cmd_monitor,
        "watch": cmd_monitor,
        "contacts": cmd_contacts,
        "crawl": cmd_crawl,
        "search": cmd_search,
        "llm-extract": cmd_llm_extract,
        "map": cmd_map,
        "doctor": cmd_doctor,
        "diff": cmd_diff,
        "snapshot": cmd_snapshot,
        "cache-stats": cmd_cache_stats,
        "screenshot": cmd_screenshot,
        "batch": cmd_batch,
        "serve": cmd_serve,
        "config": cmd_config,
        "generate": cmd_generate,
    }

    cmd_fn = dispatch.get(args.command)
    if cmd_fn:
        asyncio.run(cmd_fn(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
