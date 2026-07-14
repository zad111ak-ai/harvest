# 🌾 Harvest — Open-Source AI Web Scraper

[![GitHub Stars](https://img.shields.io/github/stars/zad111ak-ai/harvest?style=social)](https://github.com/zad111ak-ai/harvest)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python)](https://python.org)
[![Scrapling](https://img.shields.io/badge/scrapling-0.4.9%2B-FF6B35?logo=python)](https://github.com/DoreenR/Scrapling)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/zad111ak-ai/harvest?logo=github)](https://github.com/zad111ak-ai/harvest/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/zad111ak-ai/harvest/ci.yml?logo=github)](https://github.com/zad111ak-ai/harvest/actions)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000)](https://github.com/astral-sh/ruff)
[![BTC](https://img.shields.io/badge/donate-BTC-F7931A?logo=bitcoin)](https://blockchain.info/address/bc1qd8sa7e4f696wmcyszuxh9snqt2n66zrhz9g80j)
[![ETH](https://img.shields.io/badge/donate-ETH-8C8CFF?logo=ethereum)](https://etherscan.io/address/0xD26f0efE6A8F11e127c3Af3D6163BD458a1693c3)
[![SOL](https://img.shields.io/badge/donate-SOL-9945FF?logo=solana)](https://solscan.io/account/99EtqBVTeF5UNp9a1oPi18iVXbXptTG7YQ6JeJvXMUJK)

**Free, open-source alternative to Firecrawl, Crawl4AI, and ScrapeGraphAI.**  
Extract structured data from any website — bypasses Cloudflare, uses LLM for natural-language extraction, and runs as an MCP server for AI agents. **No API keys required, no cloud, 100% local.**

![Logo](./new_logo.jpg)

---

## Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Commands](#commands)
- [LLM Extraction](#-llm-extraction)
- [Preprocessing Modes](#preprocessing-modes)
- [Python API](#python-api)
- [MCP Server](#mcp-server-for-ai-agents)
- [Configuration](#configuration)
- [Benchmark](#benchmark-harvest-vs-crawl4ai-vs-firecrawl)
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Changelog](#changelog)
- [License](#license)

---

## Quick Start

```bash
pip install scrapling aiohttp
git clone https://github.com/zad111ak-ai/harvest
cd harvest
pip install -e .

# Full page content
harvest scrape https://news.ycombinator.com

# Structured data by CSS
harvest extract https://books.toscrape.com \
  --schema '{"title": "h3 a", "price": ".price_color"}'

# Structured data by AI (describe in plain language)
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

# Discover all URLs
harvest map https://docs.example.com

# Check installation
harvest doctor
```

---

## Features

### Core

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

### Intelligence (v0.6.3+)

| Feature | Description |
|---|---|
| **🧠 Semantic Cache** | Meaning-based cache, saves 50-70% LLM tokens |
| **🔧 Self-Healing Parsers** | Auto-regenerate broken CSS selectors via LLM |
| **📊 Structural Diff** | DOM change detection with human-readable summary |
| **🤖 Script Generator** | Analyze once with LLM, generate standalone scraper — 0 tokens at runtime |
| **⚡ Preprocessing Modes** | 4 modes (full/economy/hybrid/auto) for different use cases |

---

## Commands

| Command | Description |
|---|---|
| `harvest scrape <url>` | Page content as Markdown/text/HTML |
| `harvest extract <url> --schema JSON` | Structured data by CSS selectors |
| `harvest llm-extract <url> --prompt TEXT` | **Structured data by AI description** |
| `harvest llm-extract --prompt TEXT --semantic-cache` | AI extraction with token caching |
| `harvest llm-extract --prompt TEXT --self-healing` | AI extraction with auto-healing selectors |
| `harvest monitor <url>` | Track page changes with diffs |
| `harvest crawl <url> --max-pages N` | Crawl entire site |
| `harvest map <url>` | Discover all URLs (sitemap + robots + links) |
| `harvest contacts <url>` | Emails, social links, phones |
| `harvest batch <file> --concurrency N` | Process many URLs |
| `harvest pipeline "scrape URL \| extract SCHEMA"` | Chain operations |
| `harvest screenshot <url>` | Full-page screenshot |
| `harvest search <query>` | Web search |
| `harvest doctor` | Check installation health |
| `harvest snapshot <url>` | Capture DOM structure for diff |
| `harvest diff <url> <old> <new>` | Compare DOM snapshots |
| `harvest cache-stats` | Semantic cache statistics |
| `harvest generate <url> --fields F1 F2` | Generate standalone scraping script |
| `harvest-mcp` | MCP server for AI agents |

---

## ✨ LLM Extraction

**The killer feature.** Describe what you want in plain language — no CSS selectors needed.

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

**How it works:**
1. Harvest scrapes the page through Cloudflare
2. Content is sent to a local LLM (via OmniRoute, Ollama, or any OpenAI-compatible API)
3. LLM returns structured JSON — no regex, no CSS, no pain

**Zero external API costs.** Works with any local LLM endpoint:

```yaml
# ~/.harvest/config.yaml
llm:
  base_url: "http://localhost:3000/v1"  # OmniRoute, Ollama, etc.
  model: "auto/best-chat"
  api_key: "sk-..."
```

### Semantic Cache

**Save 50-70% LLM tokens** on repeated queries. Cache works by *meaning*, not exact text.

```bash
# Enable semantic cache
harvest llm-extract https://shop.com --prompt "Get all prices" --semantic-cache

# Check cache stats
harvest cache-stats
```

**How it works:**
1. First query: "Extract all product prices" → LLM → result cached
2. Second query: "Get product prices" → **cache hit** (0 tokens used)
3. If the HTML content changes, the cache auto-invalidates

### Self-Healing Parsers

**Never lose data to website changes.** Auto-regenerate broken CSS selectors via LLM.

```bash
harvest llm-extract https://shop.com --prompt "Get prices" --self-healing
```

**How it works:**
1. Test existing selectors on new HTML
2. If broken → send old/new HTML to LLM
3. LLM generates new selectors
4. Validate new selectors → save if working

### Script Generator

**Zero-token scraping.** Analyze a page with LLM once, generate a standalone Python script that extracts the same data forever.

```bash
# Analyze and generate (one-time LLM cost)
harvest generate https://shop.com --fields title price image

# Run generated script — no LLM needed
./scrape_generated.py https://shop.com/page/123

# Batch mode
./scrape_generated.py urls.txt --csv prices.csv
```

| Before (LLM every time) | After (one LLM, zero forever) |
|---|---|
| `harvest llm-extract` — 2K tokens/run | `harvest generate` — one-time 4K tokens |
| 1000 runs = 2M tokens ($0.30–$2.00) | 1000 runs = **$0.00** |
| Needs LLM endpoint running | Pure Python + Scrapling, runs anywhere |
| Slow (LLM latency per call) | Fast (HTTP + BeautifulSoup) |

---

## Preprocessing Modes

Harvest has 4 preprocessing modes. **Default is `full`** — safe, zero data loss.

| Mode | Token savings | Data loss risk | Best for |
|---|---|---|---|
| `full` | 0-40% | ❌ None | Default. Debugging. When you need every byte. |
| `economy` | 70-90% | ⚠️ Low | LLM extraction. RAG systems. Embeddings. |
| `hybrid` | 85-95% | ⚠️ Low | AI agents. Structured extraction pipelines. |
| `auto` | varies | ⚠️ Low | Smart detection. Picks best mode per page. |

```bash
# Full mode (default, preserves everything)
harvest scrape https://example.com

# Economy mode for LLM
harvest scrape https://shop.com --mode economy

# Hybrid: economy + extraction context for AI
harvest llm-extract https://shop.com --mode hybrid --prompt "Get all products"

# Auto: smart detection
harvest scrape https://any-site.com --mode auto
```

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

    # With semantic cache
    from harvest import SemanticCache
    cache = SemanticCache()
    cached = cache.get("https://shop.com", "Get all prices")
    if not cached:
        result = await llm.extract(
            url="https://shop.com",
            description="Get all prices",
        )
        cache.set("https://shop.com", "Get all prices",
                  html=result.get("content", ""),
                  response=result.get("extracted", {}))

asyncio.run(main())
```

### Key Classes

| Class | Purpose |
|---|---|
| `Scraper` | Full-page scraper with Cloudflare bypass, caching, rate limiting |
| `SchemaExtractor` | CSS-selector-based structured extraction |
| `LLMExtractor` | AI-powered natural language extraction |
| `SemanticCache` | Meaning-based response cache (saves LLM tokens) |
| `ResponseCache` | TTL-based response cache for page content |
| `ChangeWatcher` | Page change detection with diffs |
| `SiteCrawler` | Full-site crawling with sitemap support |
| `ContactCollector` | Email/social link extraction |

---

## MCP Server for AI Agents

Harvest exposes everything via **Model Context Protocol (MCP)** — works with Claude, Cursor, Hermes, and any MCP client.

```bash
pip install -e ".[mcp]"
hermes mcp add harvest --command 'harvest-mcp'
```

### Available MCP Tools

| Tool | Description |
|---|---|
| `scrape(url, extraction?)` | Scrape a page |
| `extract(url, schema)` | CSS-based extraction |
| `llm_extract(url, prompt, schema?)` | AI-based extraction |
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
  url: ""                   # Leave blank = direct
  rotation_file: ""
  rotation_interval: 10

scraper:
  rate_limit: 10             # req/min
  timeout: 30                # seconds
  retries: 3

llm:
  base_url: "http://localhost:3000/v1"
  model: "auto/best-chat"
  api_key: "sk-..."

export:
  default_format: json
  csv_delimiter: ","

notify:
  telegram_token: ""
  telegram_chat_id: ""
  webhook_url: ""
```

All fields are optional. Works out of the box with zero config.

---

## Benchmark: Harvest vs Crawl4AI vs Firecrawl

| Feature | Harvest | Crawl4AI (72k★) | Firecrawl |
|---|---|---|---|
| **Semantic Cache** | ✅ Meaning-based, 50-70% token savings | ❌ URL-only | ❌ |
| **Self-Healing Parsers** | ✅ Auto-regenerate broken selectors via LLM | ❌ | ❌ |
| **Structural Diff** | ✅ DOM change detection + summary | ❌ | ❌ |
| Cloudflare/Turnstile bypass | ✅ Built-in (Scrapling) | ⚠️ Basic | ✅ |
| LLM extraction (natural language) | ✅ Any OpenAI API | ✅ | ✅ |
| MCP server (AI agent integration) | ✅ | ❌ | ❌ |
| Preprocessing modes (4 modes) | ✅ full/economy/hybrid/auto | ❌ | ❌ |
| Anti-fingerprinting (24 UAs) | ✅ | ❌ | ✅ |
| One command, zero config | ✅ | ✅ | ✅ |
| Price | **Free** | **Free** | $50/mo |

---

## How It Works

1. **Scrapling** launches a headless Chromium with anti-detection fingerprints
2. **Cloudflare/anti-bot** challenges are solved automatically
3. **Content** is extracted from the rendered DOM
4. **LLM** parses content into structured JSON (when using `llm-extract`)
5. **Snapshots** saved locally for change detection

> Bypasses Cloudflare JS challenges and Interstitial pages. Turnhstile checkbox (behavioral biometrics) may still block — marked as "needs manual action."

---

## Requirements

- Python 3.10+
- [Scrapling](https://github.com/DoreenR/Scrapling) 0.4.9+
- Chromium (auto-downloaded by Scrapling on first use)
- Optional: any OpenAI-compatible LLM endpoint for `llm-extract`

```bash
pip install scrapling aiohttp
pip install -e .
```

---

## Changelog

### v0.6.3
- 🤖 **Script Generator** — `harvest generate <url> --fields title price`
- 🧠 **Semantic Cache** — meaning-based response cache (saves 50-70% LLM tokens)
- 🔧 **Self-Healing Parsers** — auto-regenerate broken CSS selectors via LLM
- 📊 **Structural Diff** — DOM structure change detection with human-readable summary
- 📸 `harvest snapshot` / `harvest diff` — capture and compare DOM snapshots
- 📈 `harvest cache-stats` — semantic cache statistics
- ⚡ 4 preprocessing modes — full/economy/hybrid/auto

### v0.6.1
- ✨ `harvest llm-extract` — AI-powered extraction via CLI
- ✨ `harvest map` — instant URL discovery (sitemap, robots.txt, links)
- ✨ `harvest doctor` — installation health check
- ✨ MCP: `llm_extract` and `map_urls` tools

### v0.5.0
- ✨ **LLM extraction** — describe what you want, get JSON
- 🔒 Enhanced stealth — 24 rotating UAs, randomized viewport/timezone/locale
- ⚡ Response caching — in-memory TTL cache
- 🚦 Rate limiting — token bucket, configurable
- 🔧 Persistent browser session — faster repeated scrapes

---

## License

MIT
