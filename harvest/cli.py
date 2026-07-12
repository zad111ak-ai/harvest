"""
Harvest CLI — command-line interface for the universal web collection engine.

Usage:
    harvest scrape <url> [--selector CSS] [--output json|md|txt]
    harvest monitor <url> [--selector CSS]
    harvest contacts <url>
    harvest search <query> [--source reddit|hn|all]
    harvest check <url> [--selector CSS]      # Alias for monitor
    harvest serve                              # Optional: start HTTP API
    harvest --help
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import __version__
from .core import Scraper
from .monitor import ChangeWatcher
from .contacts import ContactCollector


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harvest",
        description="Universal web collection engine — scrape, monitor, and extract data from any website.",
        epilog="Examples:\n"
        "  harvest scrape https://example.com\n"
        "  harvest scrape https://news.ycombinator.com --selector '.athing'\n"
        "  harvest monitor https://example.com/pricing\n"
        "  harvest contacts https://company.com\n"
        "  harvest search 'AI tools 2025'\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"harvest {__version__}")
    parser.add_argument("--proxy", help="HTTP proxy URL (e.g., http://127.0.0.1:1082)")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")

    sub = parser.add_subparsers(dest="command", required=True)

    # scrape
    p_scrape = sub.add_parser("scrape", help="Extract content from a URL")
    p_scrape.add_argument("url", help="Page URL")
    p_scrape.add_argument("--selector", "-s", help="CSS selector for specific elements")
    p_scrape.add_argument(
        "--output", "-o", choices=["json", "md", "txt"], default="json", help="Output format"
    )

    # monitor / check
    p_mon = sub.add_parser("monitor", help="Monitor a URL for changes", aliases=["check"])
    p_mon.add_argument("url", help="Page URL")
    p_mon.add_argument("--selector", "-s", help="CSS selector for specific elements")

    # contacts
    p_contacts = sub.add_parser("contacts", help="Find emails and contact info on a website")
    p_contacts.add_argument("url", help="Website URL")
    p_contacts.add_argument("--depth", "-d", type=int, default=2, help="How many pages to scan")

    # search
    p_search = sub.add_parser("search", help="Search across supported sources")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--source", default="all", help="Source to search (reddit, hn, all)")

    return parser


async def cmd_scrape(args):
    scraper = Scraper(proxy=args.proxy, headless=not args.no_headless)
    result = await scraper.scrape(args.url, selector=args.selector)
    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.output == "md":
        print(f"# {result.get('title', '')}")
        print()
        print(result.get("content", ""))
    elif args.output == "txt":
        title = result.get("title", "")
        content = result.get("content", "")
        if title:
            print(f"Title: {title}")
        print(content)


async def cmd_monitor(args):
    watcher = ChangeWatcher()
    result = await watcher.check(args.url, selector=args.selector)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("changed"):
        print("\n[!] CHANGE DETECTED")
        print(result.get("diff_text", ""))


async def cmd_contacts(args):
    collector = ContactCollector()
    result = await collector.collect(args.url, depth=args.depth)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nPages checked: {len(result['pages_checked'])}")
    print(f"Emails found: {len(result['emails'])}")
    print(f"Social links: {len(result['social_links'])}")


async def cmd_search(args):
    # Search via Scrapling — hit HN, Reddit, etc.
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


async def cmd_diff(args):
    watcher = ChangeWatcher()
    result = await watcher.check(args.url, selector=args.selector)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command in ("monitor", "check"):
        asyncio.run(cmd_monitor(args))
    elif args.command == "scrape":
        asyncio.run(cmd_scrape(args))
    elif args.command == "contacts":
        asyncio.run(cmd_contacts(args))
    elif args.command == "search":
        asyncio.run(cmd_search(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
