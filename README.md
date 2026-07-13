# Harvest

Universal web collection engine — extract, monitor, crawl, and search any website through Cloudflare and anti-bot protections. **Free, open-source, runs on your machine.**

![Logo](./logo.svg)

[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python)](https://python.org)
[![Scrapling](https://img.shields.io/badge/scrapling-0.4.9%2B-FF6B35?logo=python)](https://github.com/DoreenR/Scrapling)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/zad111ak-ai/harvest?logo=github)](https://github.com/zad111ak-ai/harvest/releases)
[![BTC](https://img.shields.io/badge/donate-BTC-F7931A?logo=bitcoin)](https://blockchain.info/address/bc1qd8sa7e4f696wmcyszuxh9snqt2n66zrhz9g80j)
[![ETH](https://img.shields.io/badge/donate-ETH-8C8CFF?logo=ethereum)](https://etherscan.io/address/0xD26f0efE6A8F11e127c3Af3D6163BD458a1693c3)
[![USDT](https://img.shields.io/badge/donate-USDT-26A17B?logo=tether)](https://tonviewer.com/UQAoI2i8P9-JeZhvGSUwKnymVyY5cb-1Rg7pdqoWMNena7DP)
[![SOL](https://img.shields.io/badge/donate-SOL-9945FF?logo=solana)](https://solscan.io/account/99EtqBVTeF5UNp9a1oPi18iVXbXptTG7YQ6JeJvXMUJK)

---

## Demo

```bash
# One command — full page content
harvest scrape https://news.ycombinator.com
```

```bash
# Structured data — no CSS needed
harvest llm-extract https://books.toscrape.com \
  --prompt "Get all book titles and prices"
```

```json
{
  "url": "https://books.toscrape.com",
  "title": "Books to Scrape",
  "extracted": {
    "books": [
      {"title": "A Light in the Attic", "price": "£51.77"},
      {"title": "Tipping the Velvet", "price": "£53.74"}
    ]
  }
}
```

---

## Features

| Capability | Harvest | Browse AI ($50/mo) | Octoparse ($80/mo) | ScrapingBee ($50/mo) |
|---|---|---|---|---|
| Cloudflare bypass | ✅ | ✅ | ❌ | ✅ |
| Anti-fingerprinting (24 UAs, WebGL, Canvas) | ✅ | ❌ | ❌ | ❌ |
| JS rendered pages | ✅ | ❌ | ✅ | ✅ |
| **LLM extraction (describe, not code)** | **✅** | ❌ | ❌ | ❌ |
| Structured extraction (CSS) | ✅ | ✅ | ✅ | ❌ |
| Change monitoring + diffs | ✅ | ✅ | ❌ | ❌ |
| Full site crawling | ✅ | ❌ | ✅ | ❌ |
| Contact/email collection | ✅ | ❌ | ✅ | ❌ |
| MCP server (AI agent interface) | ✅ | ❌ | ❌ | ❌ |
| Rate limiting + caching | ✅ | ❌ | ❌ | ❌ |
| **Price** | **Free** | $50/mo | $80/mo | $50/mo |

---

## Quick Start

```bash
pip install scrapling aiohttp
git clone https://github.com/zad111ak-ai/harvest
cd harvest

# Install CLI
pip install -e .

# Scrape any page
harvest scrape https://news.ycombinator.com

# Extract by CSS
harvest extract https://books.toscrape.com \
  --schema '{"title": "h3 a", "price": ".price_color"}'

# Extract by AI (describe in plain language!)
harvest llm-extract https://books.toscrape.com \
  --prompt "Get all book titles, prices, and availability"

# Monitor for changes
harvest monitor https://example.com/pricing

# Crawl entire site
harvest crawl https://docs.example.com --max-pages 100

# Find contacts
harvest contacts https://company.com

# Batch from file
harvest batch urls.txt --concurrency 10
```

---

## ✨ LLM Extraction (v0.5.0)

**The killer feature.** No other free scraping tool has this.

Instead of writing CSS selectors, just describe what you want:

```bash
# Get product data
harvest llm-extract https://shop.example.com/products \
  --prompt "Find all product names, prices, and ratings"

# Get article metadata
harvest llm-extract https://blog.example.com \
  --prompt "Extract the author, publish date, and main topics"

# Custom JSON schema
harvest llm-extract https://example.com \
  --prompt "Get company name, address, and phone" \
  --schema '{"company": "string", "address": "string", "phone": "string"}'
```

How it works:
1. Harvest scrapes the page through Cloudflare
2. Content is sent to a local LLM (via OmniRoute, Ollama, or any OpenAI-compatible API)
3. LLM returns structured JSON — no regex, no CSS, no pain

**Zero external API costs.** Works with any local LLM endpoint. Configure:

```yaml
# ~/.harvest/config.yaml
llm:
  base_url: "http://localhost:3000/v1"  # OmniRoute, Ollama, etc.
  model: "auto/best-chat"
  api_key: "sk-..."
```

---

## All Commands

| Command | Description |
|---|---|
| `harvest scrape <url>` | Page content as Markdown/text/HTML |
| `harvest extract <url> --schema JSON` | Structured data by CSS selectors |
| `harvest llm-extract <url> --prompt TEXT` | **Structured data by AI description** |
| `harvest monitor <url>` | Track page changes with diffs |
| `harvest crawl <url> --max-pages N` | Crawl entire site |
| `harvest contacts <url>` | Emails, social links, phones |
| `harvest batch <file> --concurrency N` | Process many URLs |
| `harvest pipeline "scrape URL | extract SCHEMA"` | Chain operations |
| `harvest screenshot <url>` | Full-page screenshot |
| `harvest search <query>` | Web search |
| `harvest-mcp` | MCP server for AI agents |

---

## Python API

```python
import asyncio
from harvest import Scraper, SchemaExtractor, LLMExtractor

async def main():
    # Basic scrape
    scraper = Scraper()
    result = await scraper.scrape("https://example.com")
    print(result["content"])

    # CSS extraction
    extractor = SchemaExtractor()
    data = await extractor.extract("https://shop.com", {
        "price": ".price",
        "title": "h1",
    })
    print(data["extracted"])

    # LLM extraction (describe what you want)
    llm = LLMExtractor(model="auto/best-chat")
    result = await llm.extract(
        url="https://news.ycombinator.com",
        description="Get top 10 story titles and points",
    )
    print(result["extracted"])

asyncio.run(main())
```

---

## MCP Server for AI Agents

Harvest exposes everything via **Model Context Protocol (MCP)** — works with Claude, Cursor, Hermes, and any MCP client.

```bash
# Install
pip install -e ".[mcp]"

# Test
harvest-mcp --version

# Register with Hermes
hermes mcp add harvest --command 'harvest-mcp'
```

**Available MCP tools:**

| Tool | Description |
|---|---|
| `scrape(url, extraction?)` | Scrape a page |
| `extract(url, schema)` | CSS-based extraction |
| `llm_extract(url, prompt, schema?)` | **AI-based extraction** |
| `batch(urls, concurrency?)` | Process multiple URLs |
| `contacts(url, depth?)` | Collect contacts |
| `crawl(url, max_pages?)` | Crawl a site |
| `monitor(url)` | Check for changes |
| `status()` | System info |

---

## Configuration

```yaml
# ~/.harvest/config.yaml
proxy:
  url: ""                        # Leave blank = direct
  use_scrapling: true            # Scrapling built-in proxy

scraper:
  rate_limit: "5/1s"             # 5 req/sec
  concurrency: 3                 # Parallel requests
  timeout: 30                    # Seconds
  retries: 3

llm:                             # For llm-extract command
  base_url: "http://localhost:3000/v1"
  model: "auto/best-chat"
  api_key: "sk-..."

export:
  default_format: json
```

All fields are optional. Works out of the box with zero config.

---

## How It Works

1. **Scrapling** launches a headless Chromium with anti-detection fingerprints
2. **Cloudflare/anti-bot** challenges are solved automatically
3. **Content** is extracted from the rendered DOM
4. **LLM** parses content into structured JSON (when using llm-extract)
5. **Snapshots** saved locally for change detection

> Bypasses Cloudflare JS challenges and Interstitial pages. Turnstile checkbox (behavioral biometrics) may still block — marked as "needs manual action."

---

## Requirements

- Python 3.10+
- [Scrapling](https://github.com/DoreenR/Scrapling) 0.4.9+
- Chromium (auto-downloaded)
- Optional: any OpenAI-compatible LLM endpoint for `llm-extract`

Install in 10 seconds:

```bash
pip install scrapling aiohttp
pip install -e .
```

---

## v0.5.0 Changelog

- ✨ **LLM extraction** — describe what you want, get JSON. No CSS needed
- 🔒 **Enhanced stealth** — 24 rotating User-Agents, randomized viewport/timezone/locale
- ⚡ **Response caching** — in-memory TTL cache, zero-cost repeat requests
- 🚦 **Rate limiting** — token bucket, configurable
- 🧠 **Adaptive error logging** — self-learning loop integration
- 🔧 **Persistent browser session** — faster repeated scrapes
- 🐛 CaptchaSolver import fix

---

## License

MIT
