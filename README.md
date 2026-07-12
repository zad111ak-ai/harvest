# Harvest

Universal web collection engine — extract, monitor, and search any website through Cloudflare and anti-bot protections.

![Logo](logo.svg)

<div align="center">

[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python)](https://python.org)
[![Scrapling](https://img.shields.io/badge/scrapling-0.4.9%2B-FF6B35?logo=python)](https://github.com/DoreenR/Scrapling)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/zad111ak-ai/harvest?style=social)](https://github.com/zad111ak-ai/harvest)
[![BTC](https://img.shields.io/badge/donate-BTC-F7931A?logo=bitcoin)](https://solscan.io/account/bc1qd8sa7e4f696wmcyszuxh9snqt2n66zrhz9g80j)
[![USDT](https://img.shields.io/badge/donate-USDT-26A17B?logo=tether)](https://tonviewer.com/UQAoI2i8P9-JeZhvGSUwKnymVyY5cb-1Rg7pdqoWMNena7DP)
[![SOL](https://img.shields.io/badge/donate-SOL-9945FF?logo=solana)](https://solscan.io/account/99EtqBVTeF5UNp9a1oPi18iVXbXptTG7YQ6JeJvXMUJK)

</div>

## Why Harvest

Every developer hits the same wall: you need data from a website, but it's behind Cloudflare. You try requests — blocked. You try Selenium — detected. You try API — doesn't exist.

Harvest solves this. One tool, any website, any protection level. Built on [Scrapling](https://github.com/DoreenR/Scrapling) — the same engine that bypasses Turnstile, Interstitial, and fingerprinting checks.

## Features

| Command | What it does |
|---------|-------------|
| `harvest scrape <url>` | Extract full page content as JSON, Markdown, or text |
| `harvest monitor <url>` | Track changes — first run saves baseline, next runs show diff |
| `harvest contacts <url>` | Collect emails, social links, contact pages from a website |
| `harvest search <query>` | Search across Hacker News, Reddit, and more |
| `harvest help` | List all commands |

Killer features baked in:

- **Cloudflare bypass** — Turnstile, Interstitial, fingerprinting — all automatic
- **Plugin system** — add custom sources and processors
- **Any output format** — JSON, Markdown, plain text (pipe to anything)
- **Proxy support** — rotate proxies, use SOCKS5, HTTP, whatever
- **Diff detection** — know when pricing, content, or layout changes
- **Session persistence** — cookies, login state, browser fingerprint — all preserved

## Quick Start

```bash
pip install scrapling
git clone https://github.com/zad111ak-ai/harvest
cd harvest

# Scrape any page
python harvest scrape https://news.ycombinator.com

# Monitor for changes
python harvest monitor https://example.com/pricing

# Find contacts on a website
python harvest contacts https://example.com

# Search across sources
python harvest search "your query"
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

### Scrape with CSS selector

```bash
harvest scrape https://news.ycombinator.com --selector '.athing .titleline'
```

### Monitor for changes

```bash
harvest monitor https://example.com/pricing
# First run: saves baseline
# Second run: shows what changed
```

### Collect contacts

```bash
harvest contacts https://company.com
# {"emails": ["hello@company.com"], "social_links": [...], ...}
```

### Custom proxy

```bash
harvest scrape https://example.com --proxy http://user:pass@proxy:8080
```

## API Usage

```python
import asyncio
from harvest.core import Scraper
from harvest.monitor import ChangeWatcher
from harvest.contacts import ContactCollector

async def example():
    # Scrape
    scraper = Scraper()
    result = await scraper.scrape("https://example.com")
    print(result["content"])

    # Monitor
    watcher = ChangeWatcher()
    diff = await watcher.check("https://example.com/pricing")
    print(f"Changed: {diff['changed']}")

    # Contacts
    collector = ContactCollector()
    contacts = await collector.collect("https://example.com")
    print(contacts["emails"])

asyncio.run(example())
```

## Extending with Plugins

Drop a Python file into `plugins/` directory:

```python
from harvest.plugins import PluginBase

class MyPlugin(PluginBase):
    name = "my-plugin"
    description = "Handles custom websites"

    def can_handle(self, url: str) -> bool:
        return "my-site.com" in url

    async def handle(self, url: str, **kwargs) -> dict:
        # Your extraction logic here
        return {"url": url, "data": "extracted"}
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

- [ ] HTTP API server mode (`harvest serve`)
- [ ] Docker image
- [ ] Chrome extension integration
- [ ] Diff notification via email/Telegram
- [ ] More source plugins (HN, Reddit, GitHub, LinkedIn)
- [ ] Scheduled monitoring cron helper

## License

MIT
