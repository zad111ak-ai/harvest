# Harvest P2P Network — Architecture & Design

## Vision

Harvest P2P is a **decentralized cache-sharing network** for web data. Think BitTorrent for scraped content — every node contributes and benefits.

**The problem it solves:** Individual scrapers have limited reach. One person can't scrape everything. But a network of 100 people each scraping different sources creates a collective intelligence that outperforms any single cloud API.

## Network Topology

```mermaid
graph TB
    subgraph "Harvest P2P Network"
        A["Node A<br/>(you)"] <-->|"WebSocket"| B["Node B<br/>(friend)"]
        B <-->|"WebSocket"| C["Node C<br/>(community)"]
        A <-->|"WebSocket"| C
    end

    subgraph "Shared Cache Layer"
        LA["Local Cache A"]
        LB["Local Cache B"]
        LC["Local Cache C"]
        LA <-->|"gossip"| LB
        LB <-->|"gossip"| LC
    end

    A --> LA
    B --> LB
    C --> LC

    BS["Bootstrap Server"] -.->|"discovery"| A
    BS -.->|"discovery"| B
```

## Request Flow

```mermaid
sequenceDiagram
    participant App as Application
    participant Node as Your Node
    participant Cache as Local Cache
    participant Peer as P2P Network

    App->>Node: get_p2p(url, prompt)
    Node->>Cache: check local cache

    alt Cache HIT
        Cache-->>Node: return cached data
        Node-->>App: data (fast)
    else Cache MISS
        Node->>Peer: cache_lookup (WebSocket)

        alt Peer HIT
            Peer-->>Node: cache_response + content_hash
            Node->>Node: verify_content_hash()
            Node->>Cache: store locally
            Node-->>App: data (from peer)
        else Peer MISS
            Peer-->>Node: null
            Node-->>App: None (scrape yourself)
        end
    end
```

## Data Flow — Cache Broadcast

```mermaid
sequenceDiagram
    participant App as Application
    participant Node as Your Node
    participant Cache as Local Cache
    participant Peers as P2P Network

    App->>Node: scrape + store result
    Node->>Cache: set(key, data)
    Node->>Node: compute_content_hash(data)
    Node->>Peers: broadcast(entry)

    loop Gossip to random subset
        Peers->>Peers: verify content_hash
        Peers->>Peers: store if valid
    end
```

## Content Hash Verification

```mermaid
flowchart LR
    A["Entry Data"] --> B["JSON serialize<br/>(sort_keys=True)"]
    B --> C["SHA-256 hash"]
    C --> D["content_hash field"]

    E["Received Entry"] --> F{"content_hash<br/>present?"}
    F -->|No| G["Legacy entry<br/>→ PASS"]
    F -->|Yes| H["Recompute hash<br/>from entry.data"]
    H --> I{"Hashes<br/>match?"}
    I -->|Yes| J["✅ PASS — integrity OK"]
    I -->|No| K["❌ REJECT — tampered"]
```

## Peer Reputation System

```mermaid
flowchart TD
    A["Peer Request"] --> B{"Success?"}
    B -->|Yes| C["successes += 1"]
    B -->|No| D["failures += 1"]

    C --> E["Update reputation"]
    D --> E

    E --> F["reputation = success_rate - latency_penalty"]
    F --> G{"reputation >= 0.1?"}
    G -->|Yes| H["Use new value"]
    G -->|No| I["Set floor = 0.1"]

    H --> J["Peer Selection"]
    I --> J

    J --> K["Sort by reputation desc"]
    K --> L["Query top-N peers"]
```

## Gossip Protocol

```mermaid
flowchart TD
    A["_gossip_loop<br/>(every 30s)"] --> B{"Recent entries?"}
    B -->|No| C["Skip gossip"]
    B -->|Yes| D["Select 3 random peers"]

    D --> E["For each peer"]
    E --> F["Send last 5 entries"]
    F --> G{"Success?"}
    G -->|Yes| H["Entry delivered"]
    G -->|No| I["Skip peer"]

    A --> J["Prune stale peers"]
    J --> K{"last_seen > 10min?"}
    K -->|Yes| L["Remove from peers"]
    K -->|No| M["Keep peer"]
```

## Protocol Messages

| Message | Direction | Payload | Purpose |
|---------|-----------|---------|---------|
| `hello` | Client→Server | `{peer_id, address}` | Initial handshake |
| `hello_ack` | Server→Client | `{peer_id, address, known_peers[]}` | Accept + share peers |
| `cache_lookup` | Client→Server | `{key}` | Request cache entry |
| `cache_response` | Server→Client | `{key, data, peer_id}` | Return cached data |
| `cache_update` | Broadcast | `{entry, source}` | Share new entry |
| `ping` | Either | `{}` | Keep-alive |
| `pong` | Either | `{}` | Keep-alive response |

## Security Layers

```mermaid
flowchart TD
    A["Incoming Entry"] --> B["Layer 1: Content Hash"]
    B --> C{"SHA-256 match?"}
    C -->|No| X["❌ REJECT"]
    C -->|Yes| D["Layer 2: Field Validation"]
    D --> E{"data, timestamp present?"}
    E -->|No| X
    E -->|Yes| F["Layer 3: Size Check"]
    F --> G{"< 500KB?"}
    G -->|No| X
    G -->|Yes| H["Layer 4: Age Check"]
    H --> I{"< 7 days old?"}
    I -->|No| X
    I -->|Yes| J["Layer 5: XSS/Injection"]
    J --> K{"dangerous patterns?"}
    K -->|Yes| X
    K -->|No| L["✅ ACCEPT — store locally"]
```

## Use Cases

### Community Data Pool

```mermaid
graph LR
    A["100 developers"] --> B["Scrape different sites"]
    B --> C["Binance API"]
    B --> D["CoinGecko"]
    B --> E["DeFi protocols"]
    C --> F["Shared Cache"]
    D --> F
    E --> F
    F --> G["Everyone has<br/>complete data"]
```

### Research Collaboration

```mermaid
graph LR
    A["Team of researchers"] --> B["Scrape papers"]
    B --> C["Share via P2P"]
    C --> D["Each benefits<br/>from others' work"]
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

```mermaid
timeline
    title P2P Development Roadmap
    Phase 0 : Basic P2P node + gossip ✅
    Phase 1 : Content hash + reputation ✅
    Phase 2 : DHT (distributed hash table) 🔜
    Phase 3 : NAT traversal (hole punching) 📋
    Phase 4 : End-to-end encryption 📋
    Phase 5 : Mobile node support 📋
```

## File Structure

```
harvest/p2p/
├── __init__.py          # Module exports
├── node.py              # P2PNode, PeerInfo, P2PConfig
├── error_handler.py     # Error tracking + auto-disable
└── bootstrap_server.py  # Bootstrap/discovery logic

harvest/
├── p2p_network.py       # P2PCacheNetwork (high-level API)
└── cache.py             # ResponseCache (local cache)
```

## Contributing

The P2P module needs community help:
- **NAT traversal** — hole punching for behind-firewall nodes
- **Encryption** — end-to-end encryption for shared data
- **Reputation** — trust scoring for peers
- **Mobile** — lightweight node for mobile devices

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

---

**Join the network. Share your cache. Build collective intelligence.**
