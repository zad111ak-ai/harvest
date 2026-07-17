"""Harvest CLI — argparse parser (extracted from monolithic cli.py)."""

import argparse

from .. import __version__


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
    p_crawl.add_argument(
        "--checkpoint",
        help="Checkpoint ID for crash recovery (auto-saves every 10 URLs)",
    )
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
    p_pool.add_argument(
        "--warm",
        type=int,
        default=3,
        help="Number of browsers to pre-warm (default: 3)",
    )
    p_pool.add_argument("--stats", action="store_true", help="Show pool statistics")

    # ── shadow ── Shadow DOM extraction ──
    p_shadow = sub.add_parser("shadow", help="Extract content from Shadow DOM elements")
    p_shadow.add_argument("url", help="Page URL")
    p_shadow.add_argument(
        "--structured",
        action="store_true",
        help="Return structured JSON (not flattened text)",
    )
    p_shadow.add_argument("--output", "-o", choices=["json", "txt"], default="txt", help="Output format")

    # ── memory ── Memory monitoring ──
    p_memory = sub.add_parser("memory", help="Monitor memory usage during operations")
    p_memory.add_argument("--warn", type=float, default=500, help="Warning threshold in MB (default: 500)")
    p_memory.add_argument(
        "--critical",
        type=float,
        default=1024,
        help="Critical threshold in MB (default: 1024)",
    )

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
        "--format",
        choices=["httpx", "requests", "curl"],
        default="curl",
        help="Code output format (default: curl)",
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
