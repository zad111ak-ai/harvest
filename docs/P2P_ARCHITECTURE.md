# Harvest P2P Network — Architecture & Design

## Vision

Harvest P2P is a **decentralized cache-sharing network** for web data. Think BitTorrent for scraped content — every node contributes and benefits.

**The problem it solves:** Individual scrapers have limited reach. One person can't scrape everything. But a network of 100 people each scraping different sources creates a collective intelligence that outperforms any single cloud API.

## How It Works

### Network Topology

```
┌─────────────────────────────────────────────────┐
│              Harvest P2P Network                 │
│                                                  │
│  ┌────────┐    ┌────────┐    ┌────────┐         │
│  │ Node A │◄──►│ Node B │◄──►│ Node C │  Peers  │
│  │ (you)  │    │ (friend)│    │ (community)│     │
│  └───┬────┘    └───┬────┘    └───┬────┘         │
│      │             │             │               │
│      ▼             ▼             ▼               │
│  ┌──────────────────────────────────────┐        │
│  │         Shared Cache Layer           │        │
│  │  ┌─────────┐  ┌─────────┐           │        │
│  │  │ Local   │  │ Network │           │        │
│  │  │ Cache   │◄►│ Cache   │           │        │
│  │  └─────────┘  └─────────┘           │        │
│  │  TTL · SHA-256 · Selective sharing   │        │
│  └──────────────────────────────────────┘        │
└─────────────────────────────────────────────────┘
```

### Request Flow

```
1. You request: example.com/data
2. Check local cache → HIT? Return cached version
3. Query P2P network → Any peer has it?
   → HIT: Get from peer (fast, 0ms scraping)
   → MISS: Scrape it yourself
4. Share result with network → Others benefit
5. TTL expires → Fresh data scraped when needed
```

### Protocol

Harvest P2P uses WebSocket connections with a simple JSON message protocol:

```
Node A → Node B:
{
  "type": "cache_lookup",
  "key": "sha256(example.com/data)",
  "ttl_remaining": 3600
}

Node B → Node A:
{
  "type": "cache_response",
  "key": "sha256(example.com/data)",
  "content": "...",
  "metadata": {"scraped_at": "2024-01-15T10:30:00Z"},
  "source": "node_b"
}
```

### Key Features

| Feature | Description |
|---------|-------------|
| **Gossip Protocol** | Nodes share cache metadata with neighbors |
| **TTL-based Expiration** | Cached data expires automatically |
| **Content Hashing** | SHA-256 deduplication across network |
| **Selective Sharing** | Choose what to share (privacy control) |
| **Peer Discovery** | Bootstrap servers + gossip for new nodes |
| **Error Handling** | Graceful degradation, auto-retry |
| **Persistence** | Peer list saved to disk, survives restarts |

## Use Cases

### 1. Community Data Pool
```
100 developers scrape different crypto sites:
- Node A: Binance API
- Node B: CoinGecko
- Node C: DeFi protocols
- ...

Result: Everyone has complete market data
        without hitting any single API
```

### 2. Research Collaboration
```
Team of researchers:
- Scrape academic papers
- Share findings via P2P
- Each person benefits from others' work
- No central server needed
```

### 3. Competitive Intelligence
```
Company monitoring competitors:
- Multiple departments scrape different sources
- P2P shares cache across departments
- Avoid duplicate scraping
- Fresh data for everyone
```

## Configuration

```python
from harvest.p2p.node import P2PNode, P2PConfig

config = P2PConfig(
    listen_port=8765,
    bootstrap_servers=["ws://bootstrap.harvest.network:8765"],
    max_peers=50,
    cache_ttl=3600,  # 1 hour
    share_level="public",  # or "private", "selective"
)

node = P2PNode(config)
await node.start()
```

## Privacy & Security

| Concern | Solution |
|---------|----------|
| **Data leakage** | Selective sharing — control what you share |
| **Malicious nodes** | Content hash verification |
| **MITM attacks** | WebSocket encryption (wss://) |
| **Spam** | Rate limiting per peer |
| **Tracking** | Optional anonymous mode |

## Roadmap

- [ ] v0.9: DHT for distributed hash table
- [ ] v1.0: NAT traversal (hole punching)
- [ ] v1.1: Encryption at rest
- [ ] v1.2: Reputation system
- [ ] v1.3: Mobile node support

## Technical Details

### Cache Key Format
```
sha256(url + sort(params)) → 64-char hex string
```

### Message Types
| Type | Direction | Purpose |
|------|-----------|---------|
| `hello` | Both | Initial handshake |
| `cache_lookup` | Request | Find cached data |
| `cache_response` | Response | Return cached data |
| `cache_update` | Broadcast | Share new data |
| `peer_list` | Response | Share known peers |
| `heartbeat` | Both | Keep connection alive |

### Peer Selection
Nodes are scored by:
1. **Reliability** — uptime percentage
2. **Freshness** — how recent their data is
3. **Latency** — response time
4. **Storage** — how much they share

## Contributing

The P2P module needs community help:
- **NAT traversal** — hole punching for behind-firewall nodes
- **Encryption** — end-to-end encryption for shared data
- **Reputation** — trust scoring for peers
- **Mobile** — lightweight node for mobile devices

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

---

**Join the network. Share your cache. Build collective intelligence.**
