"""Bootstrap server for Harvest P2P network.

Public relay node that helps new peers discover each other.
Run on a VPS: python -m harvest.p2p.bootstrap_server

For local testing: python bootstrap_server.py --port 8765
"""

from __future__ import annotations

import asyncio
import sys
import time
from harvest.p2p.node import P2PNode, P2PConfig


async def main(port: int = 8765) -> None:
    """Run a bootstrap relay node."""
    config = P2PConfig(
        host="0.0.0.0",
        port=port,
        bootstrap_peers=[],  # Bootstrap doesn't connect to others
    )
    node = P2PNode(config)
    await node.start()

    print(f"🔗 Bootstrap server started on port {port}")
    print(f"   Peer ID: {node.peer_id}")
    print("   Waiting for connections...")
    print()

    try:
        while True:
            await asyncio.sleep(60)
            n = len(node.peers)
            print(
                f"[{time.strftime('%H:%M:%S')}] "
                f"Peers: {n} | "
                f"Lookups: {node.lookups_received} | "
                f"Updates: {node.updates_received}"
            )
    except KeyboardInterrupt:
        print("\nShutting down...")
        await node.stop()


if __name__ == "__main__":
    port = 8765
    if len(sys.argv) > 2 and sys.argv[1] == "--port":
        port = int(sys.argv[2])
    asyncio.run(main(port))
