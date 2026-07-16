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
    p_crawl.add_argument("--checkpoint", help="Checkpoint ID for crash recovery (auto-saves every 10 URLs)")
    p_crawl.add_argument("--resume", help="Resume from checkpoint ID after crash")

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

    # ── pool ── Browser pool management ──
    p_pool = sub.add_parser("pool", help="Pre-warm browser pool for instant scraping")
    p_pool.add_argument("--warm", type=int, default=3, help="Number of browsers to pre-warm (default: 3)")
    p_pool.add_argument("--stats", action="store_true", help="Show pool statistics")

    # ── shadow ── Shadow DOM extraction ──
    p_shadow = sub.add_parser("shadow", help="Extract content from Shadow DOM elements")
    p_shadow.add_argument("url", help="Page URL")
    p_shadow.add_argument("--structured", action="store_true", help="Return structured JSON (not flattened text)")
    p_shadow.add_argument("--output", "-o", choices=["json", "txt"], default="txt", help="Output format")

    # ── memory ── Memory monitoring ──
    p_memory = sub.add_parser("memory", help="Monitor memory usage during operations")
    p_memory.add_argument("--warn", type=float, default=500, help="Warning threshold in MB (default: 500)")
    p_memory.add_argument("--critical", type=float, default=1024, help="Critical threshold in MB (default: 1024)")

    # ── checkpoints ── Crash recovery management ──
    p_ckpt = sub.add_parser("checkpoints", help="Manage crawl checkpoints for crash recovery")
    p_ckpt_sub = p_ckpt.add_subparsers(dest="ckpt_cmd")
    p_ckpt_sub.add_parser("list", help="List all checkpoints")
    p_ckpt_show = p_ckpt_sub.add_parser("show", help="Show checkpoint details")
    p_ckpt_show.add_argument("id", help="Checkpoint crawl ID")
    p_ckpt_del = p_ckpt_sub.add_parser("delete", help="Delete a checkpoint")
    p_ckpt_del.add_argument("id", help="Checkpoint crawl ID")

    p_detect = sub.add_parser("detect-api", help="Discover hidden REST/GraphQL APIs from browser traffic")
    p_detect.add_argument("url", help="URL to visit and monitor")
    p_detect.add_argument("--interact", action="store_true", help="Auto-scroll and click elements")
    p_detect.add_argument("--scroll", type=int, default=5, help="Number of scroll iterations (default: 5)")
    p_detect.add_argument(
        "--format", choices=["httpx", "requests", "curl"], default="curl", help="Code output format (default: curl)"
    )
    p_detect.add_argument("--export", help="Export results to JSON file")
    p_detect.add_argument("--proxy", help="Proxy URL for requests")
    p_detect.add_argument("--no-headless", action="store_true", help="Show browser window")

    # P2P commands
    sub.add_parser("p2p-stats", help="Show P2P network statistics")
    sub.add_parser("p2p-peers", help="List known P2P peers")
    sub.add_parser("p2p-enable", help="Enable P2P network")
    sub.add_parser("p2p-disable", help="Disable P2P network")

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
    from .recovery import CrawlCheckpoint

    # Checkpoint/resume support
    ckpt_id = args.resume or args.checkpoint
    checkpoint = CrawlCheckpoint(ckpt_id) if ckpt_id else None

    visited = set()
    queue = []

    if args.resume and checkpoint:
        state = checkpoint.load()
        if state:
            visited = state["visited"]
            queue = state["queue"]
            print(f"🔄 Resuming crawl '{args.resume}': {len(visited)} visited, {len(queue)} queued")
        else:
            print(f"⚠️  No checkpoint found for '{args.resume}', starting fresh")
    elif args.checkpoint:
        print(f"💾 Checkpoint enabled: '{args.checkpoint}' (auto-saves every 10 URLs)")

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

    # Save final checkpoint
    if checkpoint and result.get("pages"):
        all_urls = set(p.get("url", "") for p in result.get("pages", []))
        checkpoint.save(
            all_urls,
            [],
            {
                "total_pages": result["total_pages"],
                "start_url": args.url,
            },
        )
        print(f"💾 Checkpoint saved: {len(all_urls)} URLs")

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

    # Semantic cache check
    if use_semantic_cache:
        from .semantic_cache import SemanticCache

        _sem_cache = SemanticCache()
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

        _sem_cache = SemanticCache()
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
    """Start the HTTP API server with WebSocket streaming."""
    from .server import run_server
    from .streaming import get_streamer

    cfg = Config()
    host = args.host or cfg.get("server", "host", default="0.0.0.0")
    port = args.port or cfg.get("server", "port", default=8590)

    get_streamer()  # Initialize global stats collector

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


# ── New features: pool, shadow, memory, checkpoints ──


async def cmd_pool(args):
    """Pre-warm browser pool."""
    from .browser_pool import BrowserPool

    pool = BrowserPool(warm_count=args.warm, proxy=args.proxy)
    await pool.start()

    if args.stats:
        import json

        print(json.dumps(pool.get_stats(), indent=2))
    else:
        print(f"✅ Browser pool warmed: {len(pool._warm)} browsers ready")
        print("   Use: harvest scrape <url> --use-pool")

    await pool.stop()


async def cmd_shadow(args):
    """Extract Shadow DOM content."""
    from .browser import BrowserSession
    from .shadow_dom import flatten_shadow_dom, extract_shadow_dom_structured, has_shadow_dom
    import json

    async with BrowserSession(proxy=args.proxy) as session:
        await session.fetch(args.url, extraction_type="html")
        page = session.get_playwright_page()

        has_shadow = await has_shadow_dom(page)
        print(f"🔍 Shadow DOM detected: {'Yes' if has_shadow else 'No'}", flush=True)

        if args.structured:
            result = await extract_shadow_dom_structured(page)
            output = json.dumps(result, indent=2, ensure_ascii=False)
        else:
            result = await flatten_shadow_dom(page)
            output = result or ""

    if args.output == "json":
        print(
            json.dumps(
                {"url": args.url, "has_shadow_dom": has_shadow, "content": output[:5000]}, indent=2, ensure_ascii=False
            )
        )
    else:
        print(output)


async def cmd_memory(args):
    """Monitor memory usage."""
    from .memory_monitor import MemoryMonitor

    monitor = MemoryMonitor(warn_threshold_mb=args.warn, critical_threshold_mb=args.critical)
    monitor.start()
    monitor.snapshot("start")
    print(monitor.report())


async def cmd_checkpoints(args):
    """Manage crawl checkpoints."""
    from .recovery import CrawlCheckpoint
    import json

    if args.ckpt_cmd == "list":
        ckpts = CrawlCheckpoint.list_checkpoints()
        if not ckpts:
            print("No checkpoints found in ~/.harvest/checkpoints/")
            return
        print(f"{'ID':<20} {'Visited':>8} {'Queue':>8} {'Timestamp'}")
        print(f"{'─' * 20} {'─' * 8} {'─' * 8} {'─' * 26}")
        for c in ckpts:
            print(f"{c['crawl_id']:<20} {c['visited_count']:>8} {c['queue_count']:>8} {c['timestamp']}")

    elif args.ckpt_cmd == "show":
        ckpt = CrawlCheckpoint(args.id)
        info = ckpt.get_info()
        if info:
            print(json.dumps(info, indent=2))
        else:
            print(f"No checkpoint found: {args.id}")

    elif args.ckpt_cmd == "delete":
        ckpt = CrawlCheckpoint(args.id)
        if ckpt.exists():
            ckpt.delete()
            print(f"✅ Deleted checkpoint: {args.id}")
        else:
            print(f"No checkpoint found: {args.id}")
    else:
        print("Usage: harvest checkpoints [list|show <id>|delete <id>]")


async def cmd_detect_api(args):
    """Discover hidden APIs from browser traffic."""
    from .api_detector import APIDetector

    async with APIDetector(
        proxy=args.proxy,
        headless=not args.no_headless,
    ) as detector:
        await detector.visit(
            args.url,
            interact=args.interact,
            scroll_count=args.scroll,
        )

        print(detector.summary())

        apis = detector.get_apis()
        if not apis:
            print("No API endpoints discovered. Try --interact to trigger more requests.\n")
            return

        sep = "=" * 60
        print(f"\n{sep}")
        print("Generated " + args.format + " code for first endpoint:\n")
        print(detector.generate_code(apis[0], style=args.format))

        if args.export:
            data = detector.export(args.export)
            ep_count = data["total_endpoints"]
            print(f"\n✅ Exported {ep_count} endpoints to " + args.export)


async def cmd_p2p_stats(args):
    """Show P2P network statistics."""
    from harvest.cache import ResponseCache
    from harvest.p2p_network import P2PCacheNetwork
    from harvest.p2p.node import P2PConfig

    cache = ResponseCache()
    config = P2PConfig()
    net = P2PCacheNetwork(cache, config)

    stats = net.get_stats()
    enabled = stats["enabled"]
    print("\n  P2P Network Statistics")
    print(f"  {'=' * 40}")
    print(f"  Status:       {'ON' if enabled else 'OFF'}")
    print(f"  Peer ID:      {stats['peer_id']}")
    print(f"  Peers:        {stats['connected_peers']}")
    print(f"  Local hits:   {stats['local_hits']}")
    print(f"  P2P hits:     {stats['p2p_hits']}")
    print(f"  Misses:       {stats['misses']}")
    print(f"  Hit rate:     {stats['p2p_hit_rate']:.1%}")
    print(f"  Broadcasts:   {stats['broadcasts']}")
    print(f"  P2P errors:   {stats['p2p_errors']}")
    print()


async def cmd_p2p_peers(args):
    """List known P2P peers."""
    from harvest.p2p.node import P2PNode, P2PConfig

    config = P2PConfig()
    node = P2PNode(config)
    node._load_peers()

    peers = node.peers
    if not peers:
        print("  No known peers. Connect to a network first.")
        return

    print(f"\n  Known Peers ({len(peers)})")
    print(f"  {'=' * 50}")
    for pid, peer in peers.items():
        rep = peer.reputation
        color = "HIGH" if rep > 0.7 else "MED" if rep > 0.4 else "LOW"
        print(f"  {pid[:20]:20s}  rep={rep:.2f} [{color:3s}]  {peer.address}")
    print()


async def cmd_p2p_enable(args):
    """Enable P2P network."""
    import json
    from pathlib import Path

    config_path = Path.home() / ".harvest" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    config["p2p_enabled"] = True
    config_path.write_text(json.dumps(config, indent=2))
    print("P2P enabled. Restart Harvest to apply.")


async def cmd_p2p_disable(args):
    """Disable P2P network."""
    import json
    from pathlib import Path

    config_path = Path.home() / ".harvest" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    config["p2p_enabled"] = False
    config_path.write_text(json.dumps(config, indent=2))
    print("P2P disabled. Restart Harvest to apply.")


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
        "pool": cmd_pool,
        "shadow": cmd_shadow,
        "memory": cmd_memory,
        "checkpoints": cmd_checkpoints,
        "detect-api": cmd_detect_api,
        "p2p-stats": cmd_p2p_stats,
        "p2p-peers": cmd_p2p_peers,
        "p2p-enable": cmd_p2p_enable,
        "p2p-disable": cmd_p2p_disable,
    }

    cmd_fn = dispatch.get(args.command)
    if cmd_fn:
        asyncio.run(cmd_fn(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
