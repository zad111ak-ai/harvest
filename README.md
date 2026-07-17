# 🌾 Harvest — The Web Data Layer for AI Agents

<p align="center">
  <em>Scrape → P2P Cache → Semantic Search → Agent Memory</em><br>
  <strong>Your AI agent's persistent brain for web data.</strong>
</p>

<p align="center">
  <a href="https://github.com/zad111ak-ai/harvest"><img src="https://img.shields.io/github/stars/zad111ak-ai/harvest?style=social" alt="GitHub Stars"></a>
  <a href="https://pypi.org/project/harvest-agent/"><img src="https://img.shields.io/pypi/v/harvest-agent" alt="PyPI"></a>
  <a href="https://github.com/zad111ak-ai/harvest/actions"><img src="https://github.com/zad111ak-ai/harvest/workflows/CI/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python" alt="Python 3.10+">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
</p>

---

## 🤔 What is Harvest?

Harvest is a **web scraping toolkit designed for AI agents**. It's not just another crawler — it's the **data layer** between the web and your AI agent's brain.

**The problem:** AI agents forget everything between sessions. You research a topic for 3 hours, find critical data, and tomorrow the agent has no memory of it.

**The solution:** Scrape → Store in semantic memory → Agent remembers forever.

### How It's Different

| | Traditional Scrapers | Harvest |
|---|---|---|
| **Scrape** | ✅ | ✅ |
| **Store for AI** | ❌ (data dies) | ✅ Semantic memory |
| **P2P Cache** | ❌ | ✅ Community data sharing |
| **MCP Integration** | ❌ | ✅ 17 tools |
| **Privacy** | Cloud APIs | ✅ 100% local |
| **Cost** | $$$ per request | ✅ $0 forever |

---

## 🚀 Quick Start

```bash
# Install
pip install harvest-agent

# Scrape a URL
python -c "
from harvest import Harvest, CrawlConfig
h = Harvest(CrawlConfig())
result = h.scrape('https://example.com')
print(result.markdown)
"
```

### With MCP (Claude, Cursor, Hermes)

```json
{
  "mcpServers": {
    "harvest-mcp": {
      "command": "harvest-mcp",
      "args": []
    }
  }
}
```

Available tools: `harvest_scrape`, `harvest_extract`, `harvest_contacts`, `harvest_batch`, `harvest_stats`, `denseforge_search`, `denseforge_ingest`

---

## 🔥 Killer Feature: P2P Data Network

**This is what makes Harvest unique.** No other scraping tool has this.

```
Traditional:
  You scrape → You pay → You store → You forget

Harvest P2P:
  You scrape → Cache shared with network → Others benefit → Everyone wins
```

### How P2P Works

```
┌─────────────────────────────────────────────┐
│           Harvest P2P Network                │
│                                              │
│  ┌──────┐   ┌──────┐   ┌──────┐             │
│  │Node A│←→│Node B│←→│Node C│   ← Peers     │
│  └──┬───┘   └──┬───┘   └──┬───┘             │
│     │          │          │                  │
│     ▼          ▼          ▼                  │
│  ┌──────────────────────────────┐            │
│  │     Shared Cache Layer       │            │
│  │  - TTL-based expiration      │            │
│  │  - Content hashing           │            │
│  │  - Selective sharing         │            │
│  │  - Zero-knowledge proofs     │            │
│  └──────────────────────────────┘            │
│                                              │
│  Request flow:                               │
│  1. Check local cache                        │
│  2. Query P2P network (fast)                 │
│  3. If miss → scrape + share                 │
│  4. Result cached for everyone               │
└─────────────────────────────────────────────┘
```

### Why P2P Changes Everything

| Scenario | Without P2P | With P2P |
|---|---|---|
| 100 users scrape same site | 100× requests (slow, expensive) | 1 request + 99 cache hits |
| New data appears | Everyone rescrapes | First node shares, rest fetch |
| API rate limits | Hit by everyone | Distributed across network |
| Data freshness | Manual refresh | TTL + auto-invalidation |

**P2P compensates for individual limitations.** Even if your scraper is small, the network's collective scraping power is massive.

---

## 📦 Core Features

### 🕷️ Smart Scraping
- Anti-bot bypass (Cloudflare, DataDome, etc.)
- JavaScript rendering
- Metadata extraction
- Batch processing with rate limiting

### 🧠 Semantic Memory (Optional — with DenseForge)
- Triple hybrid search (keyword + vector + BM25)
- RRF fusion for better results
- Ask "why" and "what if" questions
- Persistent memory across sessions

### 🔗 MCP Integration
- 17 tools for AI agents
- Works with Claude, Cursor, Hermes, any MCP client
- Unified interface for scraping + memory

### 📊 Compliance & Security
- robots.txt respect
- GDPR-aware data handling
- SSRF protection
- Rate limiting

---

## 🛠️ Installation

```bash
# Basic
pip install harvest-agent

# With semantic memory (optional)
pip install harvest-agent[denseforge]

# Development
git clone https://github.com/zad111ak-ai/harvest
cd harvest
pip install -e ".[dev]"
```

---

## 📖 Usage Examples

### Basic Scraping
```python
from harvest import Harvest, CrawlConfig

config = CrawlConfig(
    max_concurrent=5,
    respect_robots_txt=True
)

h = Harvest(config)
result = h.scrape("https://news.ycombinator.com")

print(result.markdown)  # Clean markdown
print(result.metadata)  # Title, links, etc.
```

### Batch Processing
```python
urls = [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3"
]

results = h.batch_scrape(urls, max_concurrent=3)
for result in results:
    print(f"{result.url}: {len(result.markdown)} chars")
```

### Contact Extraction
```python
from harvest import Harvest

h = Harvest()
result = h.scrape("https://company-website.com/contact")

contacts = h.extract_contacts(result)
print(contacts.emails)    # ['info@company.com']
print(contacts.phones)    # ['+1-555-0123']
print(contacts.socials)   # ['linkedin.com/company']
```

### With DenseForge (Optional)
```python
from harvest import Harvest
from harvest.integrations.denseforge import DenseForgeBridge

# Scrape
h = Harvest()
result = h.scrape("https://docs.python.org/3/tutorial")

# Store in semantic memory
bridge = DenseForgeBridge()
bridge.store(result.markdown, metadata={"source": result.url})

# Search later
results = bridge.search("how to use classes")
```

---

## 🏗️ Architecture

```
harvest/
├── __init__.py          # Main Harvest class
├── core.py              # Core scraping logic
├── security.py          # SSRF protection, rate limiting
├── compliance.py        # GDPR, robots.txt
├── api_detector.py      # API endpoint discovery
├── mcp_server.py        # MCP integration (17 tools)
├── p2p/                 # P2P network module
│   ├── __init__.py
│   ├── node.py          # P2P node implementation
│   ├── cache.py         # Shared cache layer
│   └── sync.py          # Synchronization protocol
└── integrations/
    └── denseforge.py    # DenseForge bridge (optional)
```

---

## 🤝 Contributing

We're building the **future of AI agent data**. Join us!

### Areas for Help
- 🐛 Bug fixes
- 📝 Documentation
- 🧪 Tests
- 🌐 P2P protocol improvements
- 🔌 New integrations

### Development
```bash
git clone https://github.com/zad111ak-ai/harvest
cd harvest
pip install -e ".[dev]"
pytest tests/
```

---

## 📜 License

MIT License — use it however you want.

---

## ☕ Support

If Harvest saves you time/money, consider buying me a coffee:

- **BTC:** `bc1qd8sa7e4f696wmcyszuxh9snqt2n66zrhz9g80j`
- **ETH:** `0xD26f0efE6A8F11e127c3Af3D6163BD458a1693c3`
- **USDT (TON):** `UQAoI2i8P9-JeZhvGSUwKnymVyY5cb-1Rg7pdqoWMNena7DP`
- **SOL:** `99EtqBVTeF5UNp9a1oPi18iVXbXptTG7YQ6JeJvXMUJK`
- **X/Twitter:** [@JosephPost2](https://x.com/JosephPost2)

---

<p align="center">
  <strong>🌾 Harvest — Your AI agent never forgets.</strong>
</p>
