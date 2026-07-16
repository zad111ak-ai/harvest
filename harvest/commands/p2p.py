"""P2P and cache commands: cache-stats, p2p-stats, p2p-peers, p2p-enable, p2p-disable."""

import json
from pathlib import Path


async def cmd_cache_stats(args):
    """Show semantic cache statistics."""
    from ..semantic_cache import SemanticCache

    cache = SemanticCache()
    print(json.dumps(cache.stats(), indent=2, ensure_ascii=False))


async def cmd_p2p_stats(args):
    """Show P2P network statistics."""
    from harvest.cache import ResponseCache
    from harvest.p2p_network import P2PCacheNetwork
    from harvest.p2p.node import P2PConfig

    cache = ResponseCache()
    config = P2PConfig()
    net = P2PCacheNetwork(cache, config)

    stats = net.get_stats()
    enabled = stats["enabled"]
    print("\n  P2P Network Statistics")
    print(f"  {'=' * 40}")
    print(f"  Status:       {'ON' if enabled else 'OFF'}")
    print(f"  Peer ID:      {stats['peer_id']}")
    print(f"  Peers:        {stats['connected_peers']}")
    print(f"  Local hits:   {stats['local_hits']}")
    print(f"  P2P hits:     {stats['p2p_hits']}")
    print(f"  Misses:       {stats['misses']}")
    print(f"  Hit rate:     {stats['p2p_hit_rate']:.1%}")
    print(f"  Broadcasts:   {stats['broadcasts']}")
    print(f"  P2P errors:   {stats['p2p_errors']}")
    print()


async def cmd_p2p_peers(args):
    """List known P2P peers."""
    from harvest.p2p.node import P2PNode, P2PConfig

    config = P2PConfig()
    node = P2PNode(config)
    node._load_peers()

    peers = node.peers
    if not peers:
        print("  No known peers. Connect to a network first.")
        return

    print(f"\n  Known Peers ({len(peers)})")
    print(f"  {'=' * 50}")
    for pid, peer in peers.items():
        rep = peer.reputation
        color = "HIGH" if rep > 0.7 else "MED" if rep > 0.4 else "LOW"
        print(f"  {pid[:20]:20s}  rep={rep:.2f} [{color:3s}]  {peer.address}")
    print()


async def cmd_p2p_enable(args):
    """Enable P2P network."""
    print("⚠️  WARNING: P2P shares cache data (URL hashes, query embeddings) with other nodes.")
    print("   Disable PII in your queries and avoid sensitive data.")
    print("   Use 'harvest p2p-disable' to turn off.\n")
    config_path = Path.home() / ".harvest" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    config["p2p_enabled"] = True
    config_path.write_text(json.dumps(config, indent=2))
    print("P2P enabled. Restart Harvest to apply.")


async def cmd_p2p_disable(args):
    """Disable P2P network."""
    config_path = Path.home() / ".harvest" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    config["p2p_enabled"] = False
    config_path.write_text(json.dumps(config, indent=2))
    print("P2P disabled. Restart Harvest to apply.")
