# 🌐 P2P Cache Network

Decentralized cache sharing between Harvest users. Each PC = peer. No central server.

## How It Works

```
┌─────────────────────────────────────────┐
│           Harvest Instance              │
├─────────────────────────────────────────┤
│  ResponseCache (local)                  │
├─────────────────────────────────────────┤
│  P2PCacheNetwork (NEW)                  │
│  ├── WebSocket Client (connect peers)   │
│  ├── WebSocket Server (serve requests)  │
│  ├── DHT-lite (key→peer lookup)         │
│  └── Gossip (broadcast updates)         │
├─────────────────────────────────────────┤
│  Bootstrap Peers (relay nodes)          │
└─────────────────────────────────────────┘
```

## Usage

```bash
# P2P enabled by default — just use Harvest normally
harvest scrape https://example.com --prompt "Extract price"

# P2P statistics
harvest p2p-stats

# List connected peers
harvest p2p-peers

# Disable P2P
harvest p2p-disable

# Re-enable P2P
harvest p2p-enable
```

## As a Library

```python
from harvest.p2p_network import P2PCacheNetwork
from harvest.p2p.node import P2PConfig
from harvest.cache import ResponseCache

cache = ResponseCache()
config = P2PConfig(enabled=True, port=8765)
p2p = P2PCacheNetwork(cache, config)

await p2p.start()

# Local + P2P lookup
result = await p2p.get_p2p("https://example.com", "extract price")

# Save + broadcast
await p2p.set_p2p("https://example.com", "extract price", {"price": 42})
```

## Privacy

- **Shared**: embeddings (vectors), scraped data (sanitized)
- **NOT shared**: prompts, user IDs, request history
- PII (emails, tokens, passwords) stripped before broadcast
- All anonymous — no way to trace users

## Graceful Degradation

If P2P is unavailable, Harvest works normally with local cache only. No crashes, no data loss.

## Bootstrap Server

To run your own relay node:

```bash
python -m harvest.p2p.bootstrap_server --port 8765
```

## Architecture

- **WebSocket** for simplicity (libp2p migration planned at 100+ users)
- **Port auto-selection** (8765-8774 range)
- **Peer persistence** (survives restarts via `~/.harvest/p2p_peers.json`)
- **Error handler** with auto-disable after 10 consecutive failures + 5min cooldown
- **Fan-out lookup** to top-5 peers by reputation
- **Gossip broadcast** to random 3 peers per update
