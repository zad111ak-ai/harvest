# Changelog

All notable changes to Harvest will be documented in this file.

## v0.8.0 (2026-07-16)

### 🌐 P2P Decentralized Cache Network
- **P2PNode**: WebSocket server+client, each PC = peer in the network
- **DHT-lite**: Fan-out lookup to top-5 peers by reputation
- **Gossip protocol**: Broadcast updates to random 3 peers
- **Privacy**: PII stripping, embeddings-only sharing, no prompts leaked
- **Graceful degradation**: P2P down → Harvest works locally, no crashes
- **Peer persistence**: Survives restarts via `~/.harvest/p2p_peers.json`
- **Auto-port selection**: 8765-8774 range, no conflicts
- **Auto-disable**: After 10 consecutive errors + 5min cooldown
- **Bootstrap server**: Relay node for peer discovery (`harvest p2p-bootstrap`)
- **CLI**: `p2p-stats`, `p2p-peers`, `p2p-enable`, `p2p-disable`
- **24 tests**, all passing

### 🔍 API Reverse Engineering Agent
- **`harvest detect-api`**: Discover hidden REST/GraphQL APIs from browser traffic
- Live network interception via patchright (request + response capture)
- Automatic endpoint detection: REST (`/api/`, `/v1/`), GraphQL, WebSocket
- Code generation: httpx and curl output formats
- JSON export with full metadata
- Tested on Twitch (GraphQL), GitHub (REST), and 50+ other sites

### ⚡ Improvements
- Version bumped to v0.8.0
- README completely rewritten (bilingual RU/EN)
- 139 tests total, all passing

## v0.7.0 (2026-07-15)

### 🔍 API Reverse Engineering Agent
- `harvest detect-api` command
- Live network interception via patchright
- REST/GraphQL/WebSocket detection
- httpx/curl code generation

## v0.6.3 (2026-07-14)

- 🤖 **Script Generator** — analyze once, scrape forever (0 tokens)
- 🧠 **Semantic Cache** — meaning-based response cache (50-70% savings)
- 🔧 **Self-Healing Parsers** — auto-regenerate broken CSS selectors
- 📊 **Structural Diff** — DOM structure change detection
- 📸 **`harvest snapshot`** — capture DOM structure
- 📊 **`harvest diff`** — compare snapshots
- 📈 **`harvest cache-stats`** — semantic cache statistics
- ⚡ **4 preprocessing modes** — full/economy/hybrid/auto

## v0.6.1

- ✨ **`harvest llm-extract`** — AI-powered extraction via CLI
- ✨ **`harvest map`** — Instant URL discovery
- ✨ **`harvest doctor`** — Installation health check
- ✨ **MCP: `llm_extract` tool** — AI extraction via MCP
- ✨ **MCP: `map_urls` tool** — URL discovery via MCP

## v0.5.0

- ✨ **LLM extraction** — describe what you want, get JSON
- 🔒 **Enhanced stealth** — 24 rotating User-Agents
- ⚡ **Response caching** — in-memory TTL cache
- 🚦 **Rate limiting** — token bucket, configurable
- 🧠 **Adaptive error logging**
- 🔧 **Persistent browser session**
