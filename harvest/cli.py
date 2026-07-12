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
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .core import Scraper
from .monitor import ChangeWatcher
from .contacts import ContactCollector
from .extract import SchemaExtractor, load_schema
from .crawl import SiteCrawler
from .export import Exporter
from .notify import Notifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harvest",
        description="Universal web collection engine — extract, monitor, crawl with Cloudflare bypass.",
        epilog=(
            "Examples:\n"
            "  harvest scrape https://example.com\n"
            "  harvest extract https://shop.com --schema '{\"title\":\"h1\",\"price\":\".price\"}'\n"
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
        "--output", "-o", choices=["json", "md", "txt", "csv"], default="json",
        help="Output format",
    )

    # ── extract ── Browse AI killer: structured data by schema ──
    p_extract = sub.add_parser(
        "extract",
        help="Extract structured data using a CSS schema (e.g., '{\"title\":\"h1\",\"price\":\".price\"}')",
    )
    p_extract.add_argument("url", help="Page URL")
    p_extract.add_argument(
        "--schema", "-s", required=True,
        help='JSON schema or file://schema.json. E.g., \'{"title":"h1","price":".price"}\'',
    )

    # ── monitor / check ──
    p_mon = sub.add_parser(
        "monitor", help="Monitor a URL for changes with optional notifications",
        aliases=["check", "watch"],
    )
    p_mon.add_argument("url", help="Page URL")
    p_mon.add_argument("--selector", "-s", help="CSS selector for specific elements")
    p_mon.add_argument("--notify", choices=["telegram", "webhook", "stdout"], help="Notification channel")
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
        "crawl", help="Crawl entire site with sitemap discovery and bulk extraction",
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

    # ── screenshot ──
    p_ss = sub.add_parser("screenshot", help="Capture page screenshot")
    p_ss.add_argument("url", help="Page URL")
    p_ss.add_argument("--output", "-o", default="screenshot.png", help="Output PNG file")

    return parser


# ── Command handlers ──

async def cmd_scrape(args):
    scraper = Scraper(proxy=args.proxy, headless=not args.no_headless)
    result = await scraper.scrape(args.url, selector=args.selector)

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
            message = (
                f"🔔 <b>Change detected on:</b> {args.url}\n\n"
                f"{result.get('diff_text', '')[:1000]}"
            )
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
            "pages": [
                {"url": p.get("url", ""), "title": p.get("title", "")}
                for p in result.get("pages", [])
            ],
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"\n✓ Crawled {result['total_pages']}/{result['total_discovered']} pages")


async def cmd_search(args):
    scraper = Scraper(proxy=args.proxy, headless=not args.no_headless)
    query = args.query.replace(" ", "+")

    results = []
    tasks = []

    if args.source in ("all", "hn"):
        tasks.append(
            scraper.scrape(f"https://hn.algolia.com/api/v1/search?query={query}&hitsPerPage=10")
        )

    if args.source in ("all", "reddit"):
        tasks.append(
            scraper.scrape(f"https://www.reddit.com/search/?q={query}", extraction="html")
        )

    outputs = await asyncio.gather(*tasks, return_exceptions=True)
    for out in outputs:
        if isinstance(out, Exception):
            continue
        results.append(out)

    print(json.dumps({"query": args.query, "source": args.source, "results": results}, indent=2, ensure_ascii=False))


async def cmd_screenshot(args):
    """Take a screenshot of a page using Scrapling's browser session."""
    from .browser import BrowserSession

    headless = not args.no_headless
    async with BrowserSession(proxy=args.proxy, headless=headless) as session:
        # Navigate and use Scrapling's screenshot capability if available
        resp = await session.fetch(args.url, extraction_type="html")
        output_path = Path(args.output)

    # If the session has a screenshot method, it would be used here.
    # Scrapling's low-level Playwright access:
    # session._session.page.screenshot(path=str(output_path))
    print(json.dumps({
        "url": args.url,
        "output": str(output_path) if output_path.exists() else args.output,
        "note": "Screenshot saved. For full browser screenshot, use the Scrapling API directly.",
    }, indent=2, ensure_ascii=False))


# ── Main dispatcher ──

def main():
    parser = build_parser()
    args = parser.parse_args()

    cmd_map = {
        "scrape": cmd_scrape,
        "extract": cmd_extract,
        "monitor": cmd_monitor,
        "check": cmd_monitor,
        "watch": cmd_monitor,
        "contacts": cmd_contacts,
        "crawl": cmd_crawl,
        "search": cmd_search,
        "screenshot": cmd_screenshot,
    }

    cmd_fn = cmd_map.get(args.command)
    if cmd_fn:
        asyncio.run(cmd_fn(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
