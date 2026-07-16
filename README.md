# 🌾 Harvest v0.8.0

<p align="center">
  <a href="#russian">🇷🇺 Русский</a> &nbsp;|&nbsp; <a href="#english">🇬🇧 English</a>
</p>

[![GitHub Stars](https://img.shields.io/github/stars/zad111ak-ai/harvest?style=social)](https://github.com/zad111ak-ai/harvest)
[![GitHub contributors](https://img.shields.io/github/contributors/zad111ak-ai/harvest)](https://github.com/zad111ak-ai/harvest/graphs/contributors)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI](https://github.com/zad111ak-ai/harvest/workflows/CI/badge.svg)](https://github.com/zad111ak-ai/harvest/actions)
[![PyPI](https://img.shields.io/pypi/v/harvest-agent)](https://pypi.org/project/harvest-agent/)
[![BTC](https://img.shields.io/badge/donate-BTC-F7931A?logo=bitcoin)](https://blockchain.info/address/bc1qd8sa7e4f696wmcyszuxh9snqt2n66zrhz9g80j)
[![ETH](https://img.shields.io/badge/donate-ETH-8C8CFF?logo=ethereum)](https://etherscan.io/address/0xD26f0efE6A8F11e127c3Af3D6163BD458a1693c3)
[![USDT](https://img.shields.io/badge/donate-USDT-26A17B?logo=tether)](https://tonviewer.com/UQAoI2i8P9-JeZhvGSUwKnymVyY5cb-1Rg7pdqoWMNena7DP)
[![SOL](https://img.shields.io/badge/donate-SOL-9945FF?logo=solana)](https://solscan.io/account/99EtqBVTeF5UNp9a1oPi18iVXbXptTG7YQ6JeJvXMUJK)

---

<a id="russian"></a>

## 🇷🇺 Русский

**Бесплатный open-source веб-скрейпер** с обходом Cloudflare и LLM-экстракцией. Аналог Firecrawl и Crawl4AI, но без подписок и API-ключей. Работает на твоём компьютере, 100% локально.

### Быстрый старт

```bash
pip install harvest-agent

# Скейпинг — одна команда
harvest scrape https://example.com

# LLM-экстракция — описывай что нужно
harvest llm-extract https://shop.com \
  --prompt "Найди все цены и названия товаров"

# Обнаружение скрытых API
harvest detect-api https://shop.com

# P2P кэш — автоматически
harvest p2p-stats

# Проверка установки
harvest doctor
```

### Ключевые возможности

| Возможность | Описание |
|---|---|
| 🛡️ **Cloudflare bypass** | Обход JS-челленджей и Interstitial-страниц через Scrapling |
| 🧠 **LLM-экстракция** | Описываешь что нужно на естественном языке → получаешь JSON |
| 💾 **Semantic Cache** | Кэш по смыслу запроса (Jaccard + cosine similarity). Экономия 50–70% токенов |
| 🔧 **Self-Healing Parsers** | Если CSS-селектор сломался — LLM автоматически находит рабочий |
| 🤖 **Script Generator** | Один раз анализируешь страницу → генерируется скрипт для быстрого парсинга без LLM |
| 🔍 **API Detector** | Обнаружение скрытых REST/GraphQL API из браузерного трафика |
| 📊 **Structural Diff** | Сравнение изменений на странице — как git diff, но для DOM |
| 🌐 **P2P Cache Network** | Децентрализованный обмен кэшем между пользователями через WebSocket |
| 🔌 **MCP Server** | Интеграция с Hermes, Claude, Cursor как MCP-инструмент |
| ✨ **4 режима предобработки** | full / economy / hybrid / auto — от полного HTML до компактного текста |
| 🖥️ **Browser Pool** | Пул прелоаденных Chromium-инстансов — нет задержки на cold start |
| 💿 **Persistent Cache** | SQLite-кэш, сохраняется между перезапусками |
| ⚡ **Singleflight** | Dedup одновременных запросов — 10 параллельных → 1 реальный вызов |
| 🎯 **Embeddings Mode** | Смысловое сравнение через sentence-transformers (all-MiniLM-L6-v2) |
| 🕵️ **Anti-fingerprinting** | Рандомизация User-Agent, viewport, платформы, таймзоны |
| 🧩 **Plugin System** | Плагины для расширения функционала |
| 📡 **Notifications** | Telegram / Webhook / Stdout нотификации об изменениях |
| 🐳 **Docker** | Multi-stage сборка + docker-compose, готов к деплою |

### Все команды

| Команда | Описание |
|---|---|
| `harvest scrape <url>` | Контент страницы (Markdown/text/HTML) |
| `harvest extract <url> --schema` | CSS-экстракция по схеме |
| `harvest llm-extract <url> --prompt` | **AI-экстракция** (описание → JSON) |
| `harvest detect-api <url>` | **Обнаружение скрытых API** |
| `harvest generate <url>` | **Генерация скрипта** (0 токенов) |
| `harvest crawl <url>` | Обход всего сайта |
| `harvest contacts <url>` | Сбор email/телефонов |
| `harvest monitor <url>` | Мониторинг изменений |
| `harvest snapshot <url>` | Снимок DOM-структуры |
| `harvest diff <url> v1 v2` | Сравнение снимков |
| `harvest map <url>` | Обнаружение всех URL |
| `harvest batch <file>` | Пакетная обработка |
| `harvest cache-stats` | Статистика кэша |
| `harvest p2p-stats` | **Статистика P2P сети** |
| `harvest p2p-peers` | **Список подключённых peers** |
| `harvest serve` | **REST API сервер** (FastAPI) |
| `harvest config` | Управление конфигурацией |
| `harvest screenshot <url>` | Скриншот страницы |
| `harvest shadow <url>` | **Парсинг Shadow DOM** |
| `harvest memory` | **Мониторинг потребления RAM** |
| `harvest pool` | **Управление Browser Pool** |
| `harvest doctor` | Проверка здоровья |

### Сравнение с аналогами

| Возможность | Harvest | Crawl4AI (72k★) | Firecrawl (46k★) |
|---|---|---|---|
| Semantic Cache | ✅ 50-70% экономия | ❌ | ❌ |
| Self-Healing Parsers | ✅ | ❌ | ❌ |
| Script Generator | ✅ 0 токенов | ❌ | ❌ |
| API Detector | ✅ | ❌ | ❌ |
| P2P Cache Network | ✅ | ❌ | ❌ |
| MCP Server | ✅ | ❌ | ❌ |
| Browser Pool | ✅ | ✅ | ✅ |
| Persistent Cache | ✅ | ✅ | ✅ |
| Cloudflare bypass | ✅ | ⚠️ | ✅ |
| Docker | ✅ | ✅ | ✅ |
| Цена | **Бесплатно** | **Бесплатно** | $50/мес |

### Донаты (крипто)

| Валюта | Адрес |
|---|---|
| **BTC** | `bc1qd8sa7e4f696wmcyszuxh9snqt2n66zrhz9g80j` |
| **ETH** | `0xD26f0efE6A8F11e127c3Af3D6163BD458a1693c3` |
| **USDT (TON)** | `UQAoI2i8P9-JeZhvGSUwKnymVyY5cb-1Rg7pdqoWMNena7DP` |
| **SOL** | `99EtqBVTeF5UNp9a1oPi18iVXbXptTG7YQ6JeJvXMUJK` |

---

<a id="english"></a>

## 🇬🇧 English

**Free, open-source AI web scraper** with Cloudflare bypass & LLM extraction. An alternative to Firecrawl and Crawl4AI — no subscriptions, no API keys, 100% local.

### Quick Start

```bash
pip install harvest-agent

# Scrape — one command
harvest scrape https://example.com

# LLM extraction — describe what you need
harvest llm-extract https://shop.com \
  --prompt "Find all product names and prices"

# Detect hidden APIs
harvest detect-api https://shop.com

# P2P cache — automatic
harvest p2p-stats

# Health check
harvest doctor
```

### Key Features

| Feature | Description |
|---|---|
| 🛡️ **Cloudflare bypass** | JS challenge & Interstitial page bypass via Scrapling |
| 🧠 **LLM extraction** | Describe what you need in natural language → get structured JSON |
| 💾 **Semantic Cache** | Cache by query meaning (Jaccard + cosine similarity). 50–70% token savings |
| 🔧 **Self-Healing Parsers** | Broken CSS selectors auto-fixed by LLM |
| 🤖 **Script Generator** | Analyze once → generate a scraper script (0 tokens per run) |
| 🔍 **API Detector** | Discover hidden REST/GraphQL APIs from browser traffic |
| 📊 **Structural Diff** | Page change tracking — like git diff, but for DOM |
| 🌐 **P2P Cache Network** | Decentralized cache sharing between users via WebSocket |
| 🔌 **MCP Server** | Works with Hermes, Claude, Cursor as an MCP tool |
| ✨ **4 preprocessing modes** | full / economy / hybrid / auto — from raw HTML to compact text |
| 🖥️ **Browser Pool** | Pre-warmed Chromium instances — no cold start delay |
| 💿 **Persistent Cache** | SQLite-backed cache that survives restarts |
| ⚡ **Singleflight** | Dedup concurrent requests — 10 parallel → 1 actual call |
| 🎯 **Embeddings Mode** | Semantic comparison via sentence-transformers (all-MiniLM-L6-v2) |
| 🕵️ **Anti-fingerprinting** | Randomized User-Agent, viewport, platform, timezone |
| 🧩 **Plugin System** | Extend functionality with plugins |
| 📡 **Notifications** | Telegram / Webhook / Stdout alerts on changes |
| 🐳 **Docker** | Multi-stage build + docker-compose, ready to deploy |

### All Commands

| Command | Description |
|---|---|
| `harvest scrape <url>` | Page content (Markdown/text/HTML) |
| `harvest extract <url> --schema` | CSS extraction by schema |
| `harvest llm-extract <url> --prompt` | **AI extraction** (describe → JSON) |
| `harvest detect-api <url>` | **Discover hidden APIs** |
| `harvest generate <url>` | **Generate scraper script** (0 tokens) |
| `harvest crawl <url>` | Crawl entire site |
| `harvest contacts <url>` | Collect emails/phones |
| `harvest monitor <url>` | Track page changes |
| `harvest snapshot <url>` | Capture DOM structure |
| `harvest diff <url> v1 v2` | Compare snapshots |
| `harvest map <url>` | Discover all URLs |
| `harvest batch <file>` | Batch processing |
| `harvest cache-stats` | Cache statistics |
| `harvest p2p-stats` | **P2P network stats** |
| `harvest p2p-peers` | **List connected peers** |
| `harvest serve` | **REST API server** (FastAPI) |
| `harvest config` | Manage configuration |
| `harvest screenshot <url>` | Page screenshot |
| `harvest shadow <url>` | **Shadow DOM parsing** |
| `harvest memory` | **RAM usage monitoring** |
| `harvest pool` | **Manage Browser Pool** |
| `harvest doctor` | Health check |

### Benchmark

| Feature | Harvest | Crawl4AI (72k★) | Firecrawl (46k★) |
|---|---|---|---|
| Semantic Cache | ✅ 50-70% savings | ❌ | ❌ |
| Self-Healing Parsers | ✅ | ❌ | ❌ |
| Script Generator | ✅ 0 tokens | ❌ | ❌ |
| API Detector | ✅ | ❌ | ❌ |
| P2P Cache Network | ✅ | ❌ | ❌ |
| MCP Server | ✅ | ❌ | ❌ |
| Browser Pool | ✅ | ✅ | ✅ |
| Persistent Cache | ✅ | ✅ | ✅ |
| Cloudflare bypass | ✅ | ⚠️ | ✅ |
| Docker | ✅ | ✅ | ✅ |
| Price | **Free** | **Free** | $50/mo |

### Donations (crypto only)

| Currency | Address |
|---|---|
| **BTC** | `bc1qd8sa7e4f696wmcyszuxh9snqt2n66zrhz9g80j` |
| **ETH** | `0xD26f0efE6A8F11e127c3Af3D6163BD458a1693c3` |
| **USDT (TON)** | `UQAoI2i8P9-JeZhvGSUwKnymVyY5cb-1Rg7pdqoWMNena7DP` |
| **SOL** | `99EtqBVTeF5UNp9a1oPi18iVXbXptTG7YQ6JeJvXMUJK` |

---

## License

MIT
