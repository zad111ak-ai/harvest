# Harvest

Universal web collection engine — extract, monitor, crawl, and search any website through Cloudflare and anti-bot protections.

**Paid tools charge $50-200/mo for this. Harvest is free, open-source, and runs locally.**

![Logo](./logo.svg)

<div align="center">

[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python)](https://python.org)
[![Scrapling](https://img.shields.io/badge/scrapling-0.4.9%2B-FF6B35?logo=python)](https://github.com/DoreenR/Scrapling)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/zad111ak-ai/harvest?logo=github)](https://github.com/zad111ak-ai/harvest/releases)
[![BTC](https://img.shields.io/badge/donate-BTC-F7931A?logo=bitcoin)](https://blockchain.info/address/bc1qd8sa7e4f696wmcyszuxh9snqt2n66zrhz9g80j)
[![ETH](https://img.shields.io/badge/donate-ETH-8C8CFF?logo=ethereum)](https://etherscan.io/address/0xD26f0efE6A8F11e127c3Af3D6163BD458a1693c3)
[![USDT](https://img.shields.io/badge/donate-USDT-26A17B?logo=tether)](https://tonviewer.com/UQAoI2i8P9-JeZhvGSUwKnymVyY5cb-1Rg7pdqoWMNena7DP)
[![SOL](https://img.shields.io/badge/donate-SOL-9945FF?logo=solana)](https://solscan.io/account/99EtqBVTeF5UNp9a1oPi18iVXbXptTG7YQ6JeJvXMUJK)

</div>

## Why Harvest

Every developer hits the same wall: you need data from a website, but it's behind Cloudflare. You try `requests` — blocked. You try Selenium — detected. You try the API — it doesn't exist.

Harvest solves this. It uses [Scrapling](https://github.com/DoreenR/Scrapling) — a modern headless browser with anti-detection fingerprints, WebRTC blocking, and Canvas/WebGL spoofing — to bypass Cloudflare JS challenges and extract content from protected pages.

And unlike paid tools (Browse AI $50/mo, Octoparse $80/mo, Apify $50/mo), Harvest is **free, open-source, and runs entirely on your machine**.

## What works

| Command | Description |
|---------|-------------|
| `harvest scrape <url>` | Extract full page content as Markdown, text, or HTML |
| `harvest extract <url> --schema JSON` | **Structured extraction** — get prices, titles, ratings by CSS selectors |
| `harvest monitor <url>` | Track page changes over time (saves snapshots locally, shows diffs) |
| `harvest crawl <url>` | Find internal links and extract content from discovered pages |
| `harvest contacts <url>` | Collect emails, social links, and contact page URLs |
| `harvest batch <file>` | Process multiple URLs with concurrency control |
| `harvest pipeline "scrape URL \| extract SCHEMA"` | Chain multiple operations in one command |
| `harvest-mcp` | **MCP server** — expose all tools to AI agents (Hermes, Claude, Cursor) |

### What's built-in (no extra config)

- **Cloudflare JS challenge bypass** — Scrapling solves Interstitial and JS challenges
- **Anti-fingerprinting** — WebGL, Canvas, WebRTC are spoofed to avoid detection
- **Structured extraction** — define a CSS schema, get clean JSON. No regex, no post-processing
- **Change monitoring** — snapshots saved in `~/.harvest/`, diffs produced on subsequent runs
- **Full site crawling** — auto-discover internal links, extract every page
- **Contact collection** — email addresses, social links, phone numbers from a website
- **Batch processing** — concurrent URL processing with rate limiting
- **CSV export** — any extracted data can be exported to CSV
- **Pipeline chaining** — pipe scrape → extract → export in a single command
- **Plugin system** — add custom sources and processors

### What's planned

- HTTP API server mode (like ScrapingBee, self-hosted)
- Telegram/email alerts on monitored changes
- Docker image
- Scheduled monitoring via cron helper
- More export formats (XLSX, JSON)

## Quick Start

```bash
pip install scrapling
git clone https://github.com/zad111ak-ai/harvest
cd harvest

# Scrape any page
harvest scrape https://news.ycombinator.com

# Extract structured data
harvest extract https://books.toscrape.com --schema '{"title":"h3 a","price":".price_color"}'

# Monitor for changes
harvest monitor https://example.com/pricing

# Crawl entire site
harvest crawl https://docs.example.com --max-pages 100

# Find contacts
harvest contacts https://company.com
```

Or install as a CLI tool:

```bash
pip install -e .
harvest scrape https://news.ycombinator.com
```

## MCP Server for AI Agents

Harvest exposes all its tools via the **Model Context Protocol (MCP)** — the standard interface for AI agents (Hermes, Claude Code, Cursor, etc.).

```bash
# Install with MCP support
pip install -e ".[mcp]"

# Test it
harvest-mcp --version

# Register with your agent
hermes mcp add harvest --command 'harvest-mcp'
```

### Available MCP tools

| Tool | What it does |
|------|-------------|
| `scrape(url, selector?, extraction?)` | Scrape a page |
| `extract(url, schema)` | Structured extraction by CSS schema |
| `batch(urls, concurrency?)` | Batch process multiple URLs |
| `contacts(url, depth?)` | Collect contact information |
| `crawl(url, max_pages?)` | Crawl a website |
| `monitor(url, selector?)` | Check for page changes |
| `status()` | Get system configuration |

All tools are stateless and use stdio transport — nothing runs 24/7. The agent starts the MCP process when it needs it and stops when done.

## API Usage

```python
import asyncio
from harvest.core import Scraper
from harvest.extract import SchemaExtractor
from harvest.monitor import ChangeWatcher
from harvest.contacts import ContactCollector
from harvest.crawl import SiteCrawler

async def example():
    # Scrape
    scraper = Scraper()
    result = await scraper.scrape("https://example.com")
    print(result["content"])

    # Structured extraction
    extractor = SchemaExtractor()
    data = await extractor.extract("https://shop.com", {"price": ".price", "title": "h1"})
    print(data["extracted"])

    # Monitor
    watcher = ChangeWatcher()
    diff = await watcher.check("https://example.com/pricing")
    print(f"Changed: {diff['changed']}")

    # Crawl
    crawler = SiteCrawler(max_concurrent=5)
    pages = await crawler.crawl("https://docs.example.com", max_pages=50)
    print(f"Crawled {len(pages.get('pages', []))} pages")

asyncio.run(example())
```

## How it works

1. **Scrapling** launches a headless Chromium with anti-detection fingerprints
2. **Cloudflare challenges** (JS challenges, Interstitial) are solved automatically
3. **Content** is extracted from the rendered DOM
4. **Snapshots** are saved locally for diff detection on subsequent runs

> **Note:** Harvest can bypass Cloudflare JS challenges and Interstitial pages, but not Turnstile checkbox challenges (behavioral biometrics). Sites with Turnstile are marked as "needs manual action."

## Requirements

- Python 3.10+
- [Scrapling](https://github.com/DoreenR/Scrapling) 0.4.9+ (`pip install scrapling`)
- Chromium (auto-downloaded on first use)

## Comparison

| Feature | Harvest | Browse AI ($50/mo) | Octoparse ($80/mo) | ScrapingBee ($50/mo) |
|---------|:-------:|:------------------:|:------------------:|:--------------------:|
| Cloudflare JS bypass | ✅ | ✅ | ❌ | ✅ |
| Anti-fingerprinting | ✅ | ❌ | ❌ | ❌ |
| JS rendered pages | ✅ | ❌ | ✅ | ✅ |
| Structured extraction (CSS) | ✅ | ✅ | ✅ | ❌ |
| Change monitoring + diffs | ✅ | ✅ | ❌ | ❌ |
| Full site crawling | ✅ | ❌ | ✅ | ❌ |
| Contact/email collection | ✅ | ❌ | ✅ | ❌ |
| Batch processing | ✅ | ✅ | ✅ | ❌ |
| MCP server (AI agent interface) | ✅ | ❌ | ❌ | ❌ |
| Proxy support | ✅ | ✅ | ✅ | ✅ |
| **Price** | **Free** | $50/mo | $80/mo | $50/mo |

## License

MIT
