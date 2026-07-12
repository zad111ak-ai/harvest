# Harvest

Universal web collection engine — extract, monitor, crawl, and search any website through Cloudflare and anti-bot protections.

**Features that cost $50-200/month elsewhere — free here.**

![Logo](https://raw.githubusercontent.com/zad111ak-ai/harvest/main/logo.svg)

<div align="center">

[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python)](https://python.org)
[![Scrapling](https://img.shields.io/badge/scrapling-0.4.9%2B-FF6B35?logo=python)](https://github.com/DoreenR/Scrapling)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/zad111ak-ai/harvest?logo=github)](https://github.com/zad111ak-ai/harvest/releases)
[![GitHub stars](https://img.shields.io/github/stars/zad111ak-ai/harvest?style=social)](https://github.com/zad111ak-ai/harvest)
[![BTC](https://img.shields.io/badge/donate-BTC-F7931A?logo=bitcoin)](https://solscan.io/account/bc1qd8sa7e4f696wmcyszuxh9snqt2n66zrhz9g80j)
[![USDT](https://img.shields.io/badge/donate-USDT-26A17B?logo=tether)](https://tonviewer.com/UQAoI2i8P9-JeZhvGSUwKnymVyY5cb-1Rg7pdqoWMNena7DP)
[![SOL](https://img.shields.io/badge/donate-SOL-9945FF?logo=solana)](https://solscan.io/account/99EtqBVTeF5UNp9a1oPi18iVXbXptTG7YQ6JeJvXMUJK)

</div>

## Why Harvest

Every developer hits the same wall: you need data from a website, but it's behind Cloudflare. You try requests — blocked. You try Selenium — detected. You try API — doesn't exist.

Harvest solves this. One tool, any website, any protection level.

And unlike paid tools (Browse AI $50/mo, Octoparse $80/mo, Apify $50/mo), Harvest is **free, open-source, and runs locally on your machine**.

## vs Paid Tools

| Feature | Harvest (free) | Browse AI ($50/mo) | Octoparse ($80/mo) | ScrapingBee ($50/mo) |
|---------|:-------------:|:------------------:|:------------------:|:--------------------:|
| Cloudflare bypass | ✅ | ✅ | ❌ | ✅ |
| Turnstile solving | ✅ | ✅ | ❌ | ❌ |
| Browser fingerprinting | ✅ | ❌ | ❌ | ❌ |
| JS rendered pages | ✅ | ❌ | ✅ | ✅ |
| Structured extraction (CSS schema) | ✅ | ✅ | ✅ | ❌ |
| Change monitoring + diffs | ✅ | ✅ | ❌ | ❌ |
| Telegram alerts on changes | ✅ | ❌ | ❌ | ❌ |
| Sitemap crawl | ✅ | ❌ | ✅ | ❌ |
| Contact/email collection | ✅ | ❌ | ✅ | ❌ |
| CSV export | ✅ | ✅ | ✅ | ✅ |
| Proxy support | ✅ | ✅ | ✅ | ✅ |
| API server mode | 🔜 | ✅ | ❌ | ✅ |
| **Price** | **Free** | $50/mo | $80/mo | $50/mo |

## Features

| Command | What it does |
|---------|-------------|
| `harvest scrape <url>` | Extract full page content as JSON, Markdown, text, or CSV |
| `harvest extract <url> --schema JSON` | **Structured extraction** — like Browse AI. Get prices, titles, ratings by CSS selectors |
| `harvest monitor <url>` | Track changes — first run saves baseline, next runs show diff |
| `harvest monitor --notify telegram` | Get **Telegram alerts** when pages change (competitor pricing, docs updates) |
| `harvest crawl <url>` | **Full site crawl** with sitemap discovery, bulk export |
| `harvest contacts <url>` | Collect emails, social links, contact pages from a website |
| `harvest search <query>` | Search across Hacker News, Reddit, and more |
| `harvest screenshot <url>` | Capture page screenshot |
| `harvest help` | List all commands |

### Killer features baked in:

- **Cloudflare bypass** — Turnstile, Interstitial, fingerprinting — all automatic
- **Structured extraction** — define a schema, get clean JSON. No regex, no post-processing
- **Change alerts** — know when pricing, docs, or competitor content changes in real-time
- **Full site crawling** — auto-discover sitemap.xml, crawl every page, export to CSV
- **Plugin system** — add custom sources and processors
- **Any output format** — JSON, Markdown, CSV, plain text (pipe to anything)
- **Proxy support** — rotate proxies, use SOCKS5, HTTP, whatever
- **Session persistence** — cookies, login state, browser fingerprint — all preserved

## Quick Start

```bash
pip install scrapling
git clone https://github.com/zad111ak-ai/harvest
cd harvest

# Scrape any page
python harvest scrape https://news.ycombinator.com

# Extract structured data like Browse AI
python harvest extract https://shop.com --schema '{"title":"h1","price":".price"}'

# Monitor for changes with Telegram alert
python harvest monitor https://example.com/pricing --notify telegram --token BOT:TOKEN --chat 12345

# Crawl entire site
python harvest crawl https://docs.example.com --max-pages 100 --export docs.csv

# Find contacts and export
python harvest contacts https://company.com --export leads.csv
```

Or install as a CLI tool:

```bash
pip install -e .
harvest scrape https://news.ycombinator.com
```

## Examples

### Scrape a page

```bash
harvest scrape https://news.ycombinator.com --output md

# Output:
# Hacker News
# (page content in Markdown)
```

### Structured extraction (Browse AI killer)

```bash
harvest extract https://books.toscrape.com --schema '{"title":"h3 a","price":".price_color","availability":".availability"}'

# Output:
# {
#   "url": "https://books.toscrape.com",
#   "title": "Books to Scrape",
#   "extracted": {
#     "title": "A Light in the Attic",
#     "price": "£51.77",
#     "availability": "In stock"
#   }
# }
```

### Monitor with Telegram alert

```bash
# First run: saves baseline snapshot
harvest monitor https://competitor.com/pricing

# Second run: detects changes, sends Telegram message
harvest monitor https://competitor.com/pricing --notify telegram --token 123456:ABC-DEF --chat -1001234567890
```

### Crawl full site

```bash
harvest crawl https://docs.example.com --max-pages 200 --delay 0.3
# Finds sitemap.xml, crawls all URLs, exports results
```

### Export contacts to CSV

```bash
harvest contacts https://startup.io --export leads.csv
# Collects emails + social links, saves as CSV
```

### Custom proxy

```bash
harvest scrape https://example.com --proxy http://user:pass@proxy:8080
```

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
    crawl_result = await crawler.crawl("https://docs.example.com", max_pages=50)
    print(f"Crawled {crawl_result['total_pages']} pages")

    # Contacts
    collector = ContactCollector()
    contacts = await collector.collect("https://example.com")
    print(contacts["emails"])

asyncio.run(example())
```

## How it works

1. **Scrapling** launches a headless Chromium with anti-detection fingerprints
2. **Cloudflare challenges** are solved automatically (Turnstile, Interstitial, JS challenges)
3. **Content** is extracted, cleaned, and returned in your format
4. **Snapshots** are saved locally for diff detection on subsequent runs

## Requirements

- Python 3.10+
- [Scrapling](https://github.com/DoreenR/Scrapling) 0.4.9+ (`pip install scrapling`)
- Chromium (auto-downloaded by Playwright on first use)

## Roadmap

- [x] v0.2.0 — Structured extraction (CSS schema), full site crawl, Telegram alerts, CSV export
- [ ] HTTP API server mode (`harvest serve`)
- [ ] Docker image
- [ ] Chrome extension integration
- [ ] Webhook notifications
- [ ] More source plugins (HN, Reddit, GitHub, LinkedIn)
- [ ] Scheduled monitoring cron helper
- [ ] Proxy rotation from list
- [ ] Airtable/Google Sheets export

## License

MIT
