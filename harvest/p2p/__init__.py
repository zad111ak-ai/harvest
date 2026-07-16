"""P2P Decentralized Cache Network for Harvest.

Each Harvest instance = peer in the network. No central server.
Users anonymously share cached results → 50-90% query savings for all.

Usage:
    from harvest.p2p import P2PNode, P2PConfig

    config = P2PConfig(port=8765)
    node = P2PNode(config)
    await node.start()
"""

from .node import P2PNode
from .error_handler import P2PErrorHandler, p2p_fallback

__all__ = ["P2PNode", "P2PConfig", "P2PErrorHandler", "p2p_fallback"]
