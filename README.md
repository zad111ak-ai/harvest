# 🌾 Harvest — Open-Source AI Web Scraper with Cloudflare Bypass & LLM Extraction

[![GitHub Stars](https://img.shields.io/github/stars/zad111ak-ai/harvest?style=social)](https://github.com/zad111ak-ai/harvest)

**Free, open-source alternative to Firecrawl, Crawl4AI, and ScrapeGraphAI.** Extract structured data from any website — bypasses Cloudflare, uses LLM for natural-language extraction, and runs as an MCP server for AI agents. **No API keys required, no cloud, 100% local.**

![Logo](./new_logo.jpg)

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

## Why Harvest?
## Why Harvest?
### Benchmark: Harvest vs Crawl4AI vs Firecrawl

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
| Marketplace templates (Ozon/WB) | ✅ | ❌ | ❌ |
| Price | **Free** | **Free** | $50/mo |
**Keywords:** web scraping python, llm web scraper, cloudflare bypass scraper, mcp server scraping, open source alternative to Firecrawl, scrape without API key, python web scraping library


## 🧠 Semantic Cache (v0.6.3)

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
3. Third query: "Find prices on page" → **cache hit** (0 tokens used)

**Invalidation:** Cache auto-invalidates when HTML changes (content hash).

---

## 🔧 Self-Healing Parsers (v0.6.3)

**Never lose data to website changes.** Auto-regenerate broken CSS selectors via LLM.

```bash
# Enable self-healing
harvest llm-extract https://shop.com --prompt "Get prices" --self-healing
```

**How it works:**
1. Test existing selectors on new HTML
2. If broken → send old/new HTML to LLM
3. LLM generates new selectors
4. Validate new selectors → save if working

**History:** All selector changes stored in `~/.harvest/self_healing/`

---

## 📊 Structural Diff (v0.6.3)

**See exactly what changed** on any website. Like `git diff` for web pages.

```bash
# Capture snapshot
harvest snapshot https://shop.com --name v1.0

# Later: compare with current
harvest diff https://shop.com v1.0 latest
```

**Output:**
```
📊 Structural Diff for https://shop.com
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🆕 Added:
  • Block "Recommendations" (after description)
  • Field "Delivery" (in sidebar)

❌ Removed:
  • Field "SKU" (was in header)

🔄 Changed:
  • Price: <span class="price"> → <div class="price-container">

💡 Recommendation:
  Update selector: .price → .price-container .price-value
```

---

---

## 🤖 Script Generator (v0.6.3)

**Zero-token scraping.** Analyzes a page with LLM once to discover CSS selectors,
then generates a standalone Python script that extracts the same data forever — 0 LLM tokens at runtime.

Like ScrapeGraphAI's script generation, but you keep the script.

```bash
# Analyze a page and generate a scraper (one-time LLM cost)
harvest generate https://shop.com --fields title price image

# Generated script is fully standalone — no Harvest needed
./scrape_generated.py https://shop.com/page/123

# Batch mode
./scrape_generated.py urls.txt --csv prices.csv
```

**Why it matters:**
| Before (LLM every time) | After (one LLM, zero forever) |
|---|---|
| harvest llm-extract — 2K tokens/run | harvest generate — one-time 4K tokens |
| 1000 runs = 2M tokens ($0.30-2.00) | 1000 runs = **$0.00** |
| Needs LLM endpoint running | Pure Python + Scrapling, runs anywhere |
| Slow (LLM latency each call) | Fast (Scrapling HTTP + BeautifulSoup) |

**What's generated:**
- Self-contained Python script with hardcoded CSS selectors
- Pagination support (if detected)
- CSV/JSON export
- Batch URL processing from file
- Retry logic + random delays for anti-detection
- Stealth headers

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

**New in v0.6.3:**
| Feature | Harvest | Crawl4AI | Firecrawl |
|---|---|---|---|
| **Script Generator** | ✅ Generate standalone scripts (0 tokens) | ❌ | ❌ |

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

# Discover all URLs on a site
harvest map https://docs.example.com

# Check installation health
harvest doctor
```

---

## Preprocessing Modes (v0.6.3)

Harvest has 4 preprocessing modes for different use cases. **Default is `full`** — safe, zero data loss.

### Quick comparison

| Mode | Token savings | Data loss risk | Best for |
|---|---|---|---|
| `full` | 0-40% | ❌ None | Default. Debugging. When you need every byte. |
| `economy` | 70-90% | ⚠️ Low | LLM extraction. RAG systems. Embeddings. |
| `hybrid` | 85-95% | ⚠️ Low | AI agents. Structured extraction pipelines. |
| `auto` | varies | ⚠️ Low | Smart detection. Picks best mode per page. |

### Usage

```bash
# Default: full mode (safe, preserves everything)
harvest scrape https://example.com

# Economy: save tokens for LLM processing
harvest scrape https://shop.com --mode economy

# Hybrid: economy + extraction context for AI
harvest llm-extract https://shop.com --mode hybrid --prompt "Get all products"

# Auto: smart detection (picks best mode automatically)
harvest scrape https://any-site.com --mode auto
```

### What each mode does

**`full` (default)**
- Removes: scripts, styles, comments, hidden elements
- Keeps: ALL content, navigation, footer, sidebar, links
- Output: Markdown with all text and links preserved
- Risk: None. You get everything the page had.

**`economy`**
- Removes: nav, footer, sidebar, ads, boilerplate, duplicate content
- Keeps: main content only, links as `[text](url)`
- For catalogs: keeps first 3 items, collapses rest ("...and 47 more")
- Output: Clean Markdown, 70-90% smaller than raw
- Risk: May remove some content on unusual page layouts
- Safety: Falls back to `full` if it removes >85% on non-catalog pages

**`hybrid`**
- Everything `economy` does, PLUS:
- Adds extraction context header for LLMs
- Tells LLM: "This is a CATALOG with 20 items. Here are 3 examples. Extract all."
- Output: Economy Markdown + extraction instructions
- Risk: Same as economy. Context header adds ~200 chars.

**`auto`**
- Detects page type (article/catalog/mixed)
- Articles → uses `economy` mode
- Catalogs → uses `hybrid` mode
- Falls back gracefully if detection fails
- Risk: Same as underlying mode chosen

### ⚠️ Honest trade-offs

**What you lose with economy/hybrid:**
- Navigation menus, footers, sidebars (usually useless)
- Exact HTML structure (CSS classes, tag hierarchy)
- Text inside images (infographics, screenshots)
- Content hidden behind JS clicks ("Show phone number")

**What you keep:**
- All text content
- All links as standard `[text](url)` Markdown
- All prices, titles, descriptions
- Semantic structure (headings, paragraphs, lists)

**When to use `full`:**
- Debugging what the page actually contains
- Downstream parsers that need raw HTML structure
- Sites where economy mode removes too much
- When you're not sure what you need

**When to use `economy` or `hybrid`:**
- Sending content to LLM for extraction
- Building RAG systems or embeddings
- Processing many pages (cost savings compound)
- Catalog/listing pages with repetitive structure

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
| `harvest llm-extract <url> --prompt TEXT --semantic-cache` | **AI extraction with token caching** |
| `harvest llm-extract <url> --prompt TEXT --self-healing` | **AI extraction with auto-healing selectors** |
| `harvest monitor <url>` | Track page changes with diffs |
| `harvest crawl <url> --max-pages N` | Crawl entire site |
| `harvest map <url>` | **Discover all URLs on a site (sitemap + links)** |
| `harvest contacts <url>` | Emails, social links, phones |
| `harvest batch <file> --concurrency N` | Process many URLs |
| `harvest pipeline "scrape URL | extract SCHEMA"` | Chain operations |
| `harvest screenshot <url>` | Full-page screenshot |
| `harvest search <query>` | Web search |
| `harvest doctor` | **Check installation health** |
| `harvest snapshot <url>` | **Capture DOM structure for diff** |
| `harvest diff <url> <old> <new>` | **Compare DOM snapshots** |
| `harvest cache-stats` | **Semantic cache statistics** |
| `harvest generate <url> --fields F1 F2` | **Generate standalone scraping script (0 token cost)** |
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

## v0.6.3 Changelog

- 🤖 **Script Generator** — analyze once, scrape forever. `harvest generate <url> --fields title price`
- 🧠 **Semantic Cache** — meaning-based response cache (saves 50-70% LLM tokens)
- 🔧 **Self-Healing Parsers** — auto-regenerate broken CSS selectors via LLM
- 📊 **Structural Diff** — DOM structure change detection with human-readable summary
- 📸 **`harvest snapshot`** — capture DOM structure for later comparison
- 📊 **`harvest diff`** — compare two snapshots
- 📈 **`harvest cache-stats`** — semantic cache statistics
- ⚡ **4 preprocessing modes** — full/economy/hybrid/auto for different use cases

## v0.6.1 Changelog

- ✨ **`harvest llm-extract`** — AI-powered extraction via CLI (was advertised but missing!)
- ✨ **`harvest map`** — Instant URL discovery (sitemap, robots.txt, homepage links)
- ✨ **`harvest doctor`** — Installation health check
- ✨ **MCP: `llm_extract` tool** — AI extraction via Model Context Protocol
- ✨ **MCP: `map_urls` tool** — URL discovery via MCP

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
