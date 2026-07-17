# Harvest P2P — Design Document

## Architecture Overview

```mermaid
graph TB
    subgraph "Harvest Node"
        App["Application"]
        Cache["Local Cache<br/>(ResponseCache)"]
        P2PNet["P2P Network Layer<br/>(P2PCacheNetwork)"]
        Node["P2P Node<br/>(P2PNode)"]
    end

    subgraph "P2P Network"
        Peer1["Peer A"]
        Peer2["Peer B"]
        Peer3["Peer C"]
        Bootstrap["Bootstrap Server"]
    end

    App -->|"get(url, prompt)"| Cache
    App -->|"get_p2p(url, prompt)"| P2PNet
    P2PNet -->|"local miss?"| Node
    Node <-->|"WebSocket"| Peer1
    Node <-->|"WebSocket"| Peer2
    Node <-->|"WebSocket"| Peer3
    Node -.->|"discovery"| Bootstrap
```

## Data Flow — Cache Lookup

```mermaid
sequenceDiagram
    participant App as Application
    participant Net as P2PCacheNetwork
    participant Local as Local Cache
    participant P2P as P2P Node
    participant Peer as Remote Peer

    App->>Net: get_p2p(url, prompt)
    Net->>Local: get(key)

    alt Local HIT
        Local-->>Net: cached data
        Net-->>App: return data
    else Local MISS
        Net->>P2P: lookup(key)
        P2P->>Peer: cache_lookup (WebSocket)

        alt Peer HIT
            Peer-->>P2P: cache_response + content_hash
            P2P->>P2P: verify_content_hash()
            P2P-->>Net: verified entry
            Net->>Local: set(key, data)
            Net-->>App: return data
        else Peer MISS
            Peer-->>P2P: null
            P2P-->>Net: null
            Net-->>App: None (scrape yourself)
        end
    end
```

## Data Flow — Cache Broadcast

```mermaid
sequenceDiagram
    participant App as Application
    participant Net as P2PCacheNetwork
    participant Node as P2P Node
    participant Peer1 as Peer A
    participant Peer2 as Peer B

    App->>Net: set_p2p(url, prompt, data)
    Net->>Local: set(key, data)
    Net->>Net: sanitize_for_sharing()
    Net->>Net: compute_content_hash(data)
    Net->>Node: broadcast(entry)

    loop Gossip to random subset
        Node->>Peer1: cache_update (WebSocket)
        Node->>Peer2: cache_update (WebSocket)
    end

    Note over Peer1,Peer2: Each peer verifies content_hash
    Note over Peer1: verify_content_hash() ✓
    Note over Peer2: verify_content_hash() ✓
```

## Content Hash Verification

```mermaid
flowchart LR
    A[Entry Data] --> B[JSON serialize<br/>sort_keys=True]
    B --> C[SHA-256 hash]
    C --> D[content_hash field]

    E[Received Entry] --> F{content_hash<br/>present?}
    F -->|No| G[Legacy entry<br/>→ PASS]
    F -->|Yes| H[Recompute hash<br/>from entry.data]
    H --> I{Hashes<br/>match?}
    I -->|Yes| J[PASS — integrity OK]
    I -->|No| K[REJECT — tampered]
```

## Peer Reputation System

```mermaid
flowchart TD
    A[Peer Request] --> B{Success?}
    B -->|Yes| C[successes += 1]
    B -->|No| D[failures += 1]

    C --> E[Update reputation]
    D --> E

    E --> F["reputation = success_rate - latency_penalty"]
    F --> G{reputation >= 0.1?}
    G -->|Yes| H[Use new value]
    G -->|No| I[Set floor = 0.1]

    H --> J[Peer Selection]
    I --> J

    J --> K["Sort by reputation desc"]
    K --> L["Query top-N peers"]
```

## Gossip Protocol

```mermaid
flowchart TD
    A["_gossip_loop (every 30s)"] --> B{Recent entries?}
    B -->|No| C[Skip gossip]
    B -->|Yes| D["Select 3 random peers"]

    D --> E[For each peer]
    E --> F["Send last 5 entries"]
    F --> G{Success?}
    G -->|Yes| H[Entry delivered]
    G -->|No| I[Skip peer]

    A --> J["Prune stale peers"]
    J --> K{last_seen > 10min?}
    K -->|Yes| L[Remove from peers]
    K -->|No| M[Keep peer]
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
    A[Incoming Entry] --> B["Layer 1: Content Hash"]
    B --> C{SHA-256 match?}
    C -->|No| X[REJECT]
    C -->|Yes| D["Layer 2: Field Validation"]
    D --> E{data, timestamp present?}
    E -->|No| X
    E -->|Yes| F["Layer 3: Size Check"]
    F --> G{< 500KB?}
    G -->|No| X
    G -->|Yes| H["Layer 4: Age Check"]
    H --> I{< 7 days old?}
    I -->|No| X
    I -->|Yes| J["Layer 5: XSS/Injection"]
    J --> K{dangerous patterns?}
    K -->|Yes| X
    K -->|No| L[ACCEPT — store locally]
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

## Configuration Reference

```python
P2PConfig(
    enabled=False,           # Opt-in (default off for security)
    host="0.0.0.0",         # Listen address
    port=8765,              # Start port (tries 8765-8774)
    bootstrap_peers=[...],  # Bootstrap server URLs
    share_data=True,        # Share data with peers
    max_share_size_kb=500,  # Max entry size
    max_peers_to_query=5,   # Fan-out for lookups
    lookup_timeout_sec=5.0, # Per-peer timeout
    gossip_interval_sec=30, # Proactive gossip interval
    discovery_interval_sec=60,  # Reconnect interval
    min_peer_reputation=0.3,    # Min reputation threshold
)
```

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| Phase 0 | Basic P2P node + gossip | ✅ Done |
| Phase 1 | Content hash + reputation | ✅ Done |
| Phase 2 | DHT (distributed hash table) | 🔜 Next |
| Phase 3 | NAT traversal (hole punching) | 📋 Planned |
| Phase 4 | End-to-end encryption | 📋 Planned |
| Phase 5 | Mobile node support | 📋 Planned |

---

**Join the network. Share your cache. Build collective intelligence.**
