"""P2P Node — WebSocket-based peer for Harvest cache network.

Each node = client + server. Connects to bootstrap peers for discovery,
serves cache lookups from other peers, gossips new entries.

Architecture:
    - WebSocket server listens for incoming connections
    - WebSocket client connects to known peers
    - DHT-lite: key→peer index for cache lookup
    - Gossip: broadcast new cache entries to random subset
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("harvest.p2p")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class P2PConfig:
    """P2P network configuration."""

    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8765
    bootstrap_peers: list[str] = field(
        default_factory=lambda: [
            "ws://bootstrap1.harvest.network:8765",
            "ws://bootstrap2.harvest.network:8765",
        ]
    )

    # Privacy
    share_data: bool = True
    max_share_size_kb: int = 500

    # Performance
    max_peers_to_query: int = 5
    lookup_timeout_sec: float = 5.0
    gossip_interval_sec: float = 30.0
    discovery_interval_sec: float = 60.0

    # Reputation
    min_peer_reputation: float = 0.3

    def __post_init__(self) -> None:
        if self.bootstrap_peers is None:
            self.bootstrap_peers = []


# ---------------------------------------------------------------------------
# Peer info
# ---------------------------------------------------------------------------


@dataclass
class PeerInfo:
    """Known peer metadata."""

    peer_id: str
    address: str  # ws://host:port
    last_seen: float = 0.0
    reputation: float = 0.5


# ---------------------------------------------------------------------------
# Protocol messages
# ---------------------------------------------------------------------------

MSG_HELLO = "hello"
MSG_HELLO_ACK = "hello_ack"
MSG_CACHE_LOOKUP = "cache_lookup"
MSG_CACHE_RESPONSE = "cache_response"
MSG_CACHE_UPDATE = "cache_update"
MSG_PEER_LIST = "peer_list"
MSG_PING = "ping"
MSG_PONG = "pong"


def _make_msg(msg_type: str, **kwargs: Any) -> str:
    """Create a JSON protocol message."""
    return json.dumps({"type": msg_type, **kwargs})


# ---------------------------------------------------------------------------
# P2P Node
# ---------------------------------------------------------------------------


class P2PNode:
    """WebSocket P2P node for Harvest cache network.

    Features:
    - WebSocket server (accepts incoming peer connections)
    - WebSocket client (connects to known peers)
    - DHT-lite lookup (fan-out query to top-N peers)
    - Gossip broadcast (push new cache entries to random subset)
    - Persistent peer storage (survives restarts)
    - Port auto-selection (tries 8765-8774)
    """

    def __init__(self, config: Optional[P2PConfig] = None) -> None:
        self.config = config or P2PConfig()
        self.peer_id: str = f"harvest-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}"

        # Known peers
        self.peers: Dict[str, PeerInfo] = {}

        # Handler registry
        self._handlers: Dict[str, Callable] = {}

        # State
        self._server: Any = None
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # Metrics
        self.lookups_served = 0
        self.lookups_received = 0
        self.updates_received = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the P2P node: server + background tasks."""
        if not self.config.enabled:
            logger.info("P2P disabled in config")
            return

        self._running = True
        self._load_peers()

        # Start WebSocket server with port fallback
        for port in range(self.config.port, self.config.port + 10):
            try:
                # websockets library import
                import websockets  # noqa: F811

                self._server = await websockets.serve(
                    self._handle_connection,
                    self.config.host,
                    port,
                )
                self.config.port = port
                logger.info(f"P2P node {self.peer_id} listening on {self.config.host}:{port}")
                break
            except OSError:
                continue
        else:
            logger.warning(
                f"Could not bind ports {self.config.port}-{self.config.port + 9}, "
                "P2P server disabled (client-only mode)"
            )
            return

        # Background tasks
        self._tasks.append(asyncio.create_task(self._discovery_loop()))
        self._tasks.append(asyncio.create_task(self._gossip_loop()))
        self._tasks.append(asyncio.create_task(self._save_peers_loop()))

        # Connect to bootstrap peers
        for addr in self.config.bootstrap_peers:
            asyncio.create_task(self._connect_to_peer(addr))

    async def stop(self) -> None:
        """Gracefully stop the P2P node."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self._save_peers()
        logger.info(f"P2P node {self.peer_id} stopped")

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def on(self, event_type: str, handler: Callable) -> None:
        """Register handler for an event type.

        Supported events:
        - "cache_lookup": async fn(key: str) -> Optional[dict]
        - "cache_update": async fn(entry: dict) -> None
        """
        self._handlers[event_type] = handler

    # ------------------------------------------------------------------
    # WebSocket server (incoming connections)
    # ------------------------------------------------------------------

    async def _handle_connection(self, websocket: Any, path: str) -> None:  # noqa: ARG002
        """Handle a single incoming WebSocket connection."""
        try:
            async for message in websocket:
                await self._process_message(websocket, str(message))
        except Exception:
            pass  # Connection closed or error

    async def _process_message(self, websocket: Any, raw: str) -> None:
        """Dispatch an incoming protocol message."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type")
        if msg_type == MSG_HELLO:
            await self._on_hello(websocket, data)
        elif msg_type == MSG_CACHE_LOOKUP:
            await self._on_cache_lookup(websocket, data)
        elif msg_type == MSG_CACHE_UPDATE:
            await self._on_cache_update(data)
        elif msg_type == MSG_PEER_LIST:
            await self._on_peer_list(data)
        elif msg_type == MSG_PING:
            await websocket.send(_make_msg(MSG_PONG))
        else:
            logger.debug(f"Unknown message type: {msg_type}")

    async def _on_hello(self, websocket: Any, data: dict) -> None:
        """Respond to peer hello, exchange peer lists."""
        peer_id = data.get("peer_id", "")
        address = data.get("address", "")
        if not peer_id or not address:
            return

        self.peers[peer_id] = PeerInfo(
            peer_id=peer_id,
            address=address,
            last_seen=time.time(),
        )

        # Reply with our info + known peers
        known = [{"peer_id": p.peer_id, "address": p.address} for p in list(self.peers.values())[:10]]
        await websocket.send(
            _make_msg(
                MSG_HELLO_ACK,
                peer_id=self.peer_id,
                address=f"ws://{self.config.host}:{self.config.port}",
                known_peers=known,
            )
        )
        logger.debug(f"Hello from {peer_id}")

    async def _on_cache_lookup(self, websocket: Any, data: dict) -> None:
        """Serve a cache lookup request from a peer."""
        key = data.get("key", "")
        if not key:
            return

        self.lookups_received += 1
        handler = self._handlers.get("cache_lookup")
        result = None
        if handler:
            try:
                result = await handler(key)
            except Exception as e:
                logger.debug(f"Cache lookup handler error: {e}")

        await websocket.send(
            _make_msg(
                MSG_CACHE_RESPONSE,
                key=key,
                data=result,
                peer_id=self.peer_id,
            )
        )

    async def _on_cache_update(self, data: dict) -> None:
        """Process incoming gossip cache update."""
        self.updates_received += 1
        handler = self._handlers.get("cache_update")
        if handler:
            try:
                await handler(data)
            except Exception as e:
                logger.debug(f"Cache update handler error: {e}")

    async def _on_peer_list(self, data: dict) -> None:
        """Learn new peers from a peer list message."""
        for pinfo in data.get("peers", []):
            pid = pinfo.get("peer_id", "")
            addr = pinfo.get("address", "")
            if pid and addr and pid != self.peer_id and pid not in self.peers:
                self.peers[pid] = PeerInfo(
                    peer_id=pid,
                    address=addr,
                    last_seen=time.time(),
                )

    # ------------------------------------------------------------------
    # WebSocket client (outgoing connections)
    # ------------------------------------------------------------------

    async def _connect_to_peer(self, address: str) -> bool:
        """Connect to a peer, exchange hellos, learn new peers."""
        try:
            import websockets  # noqa: F811

            async with websockets.connect(address) as ws:
                # Send hello
                await ws.send(
                    _make_msg(
                        MSG_HELLO,
                        peer_id=self.peer_id,
                        address=f"ws://{self.config.host}:{self.config.port}",
                    )
                )

                # Wait for ack
                raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                resp = json.loads(str(raw))

                if resp.get("type") != MSG_HELLO_ACK:
                    return False

                peer_id = resp.get("peer_id", "")
                if peer_id:
                    self.peers[peer_id] = PeerInfo(
                        peer_id=peer_id,
                        address=address,
                        last_seen=time.time(),
                    )

                    # Learn their peers
                    for p in resp.get("known_peers", []):
                        pid = p.get("peer_id", "")
                        addr = p.get("address", "")
                        if pid and addr and pid != self.peer_id and pid not in self.peers:
                            self.peers[pid] = PeerInfo(
                                peer_id=pid,
                                address=addr,
                                last_seen=time.time(),
                            )

                    logger.info(f"Connected to peer {peer_id} at {address}")
                    return True

        except Exception as e:
            logger.debug(f"Failed to connect to {address}: {e}")
        return False

    async def _ask_peer(self, peer: PeerInfo, key: str) -> Optional[dict]:
        """Ask a single peer for a cache entry."""
        try:
            import websockets  # noqa: F811

            async with websockets.connect(peer.address) as ws:
                await ws.send(_make_msg(MSG_CACHE_LOOKUP, key=key))
                raw = await asyncio.wait_for(
                    ws.recv(),
                    timeout=self.config.lookup_timeout_sec,
                )
                resp = json.loads(str(raw))
                if resp.get("type") == MSG_CACHE_RESPONSE:
                    return resp.get("data")
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def lookup(self, key: str) -> Optional[dict]:
        """Fan-out lookup to top-N peers, return first hit."""
        candidates = sorted(
            self.peers.values(),
            key=lambda p: p.reputation,
            reverse=True,
        )[: self.config.max_peers_to_query]

        if not candidates:
            return None

        tasks = [self._ask_peer(p, key) for p in candidates]
        for coro in asyncio.as_completed(tasks, timeout=self.config.lookup_timeout_sec):
            try:
                result = await coro
                if result is not None:
                    return result
            except Exception:
                continue
        return None

    async def broadcast(self, entry: dict) -> None:
        """Gossip a cache entry to a random subset of peers."""
        peers = list(self.peers.values())
        if not peers:
            return

        subset = random.sample(peers, min(3, len(peers)))
        msg = _make_msg(MSG_CACHE_UPDATE, entry=entry, source=self.peer_id)

        for peer in subset:
            try:
                import websockets  # noqa: F811

                async with websockets.connect(peer.address) as ws:
                    await ws.send(msg)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Background tasks
    # ------------------------------------------------------------------

    async def _discovery_loop(self) -> None:
        """Periodically reconnect to bootstrap if peer count is low."""
        while self._running:
            await asyncio.sleep(self.config.discovery_interval_sec)
            try:
                if len(self.peers) < 5:
                    for addr in self.config.bootstrap_peers:
                        await self._connect_to_peer(addr)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Discovery error: {e}")

    async def _gossip_loop(self) -> None:
        """Placeholder for periodic gossip tasks."""
        while self._running:
            await asyncio.sleep(self.config.gossip_interval_sec)
            # Future: proactive gossip, stale entry cleanup
            await asyncio.sleep(0)  # yield

    async def _save_peers_loop(self) -> None:
        """Persist peers to disk every 5 minutes."""
        while self._running:
            await asyncio.sleep(300)
            try:
                self._save_peers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Save peers error: {e}")

    # ------------------------------------------------------------------
    # Peer persistence
    # ------------------------------------------------------------------

    def _peers_file(self) -> Path:
        return Path.home() / ".harvest" / "p2p_peers.json"

    def _save_peers(self) -> None:
        """Save known peers to disk."""
        path = self._peers_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {pid: {"address": p.address, "reputation": p.reputation} for pid, p in self.peers.items()}
        path.write_text(json.dumps(data, indent=2))

    def _load_peers(self) -> None:
        """Load peers from disk."""
        path = self._peers_file()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            for pid, info in data.items():
                self.peers[pid] = PeerInfo(
                    peer_id=pid,
                    address=info.get("address", ""),
                    reputation=info.get("reputation", 0.5),
                    last_seen=time.time(),
                )
        except Exception as e:
            logger.debug(f"Load peers error: {e}")

    # ------------------------------------------------------------------
    # Privacy
    # ------------------------------------------------------------------

    def sanitize_for_sharing(self, data: dict) -> dict:
        """Strip PII before broadcasting to peers."""
        pii_keys = {"email", "phone", "address", "password", "token", "secret", "key"}
        clean = {k: v for k, v in data.items() if not any(p in k.lower() for p in pii_keys)}

        # Truncate large strings
        max_str = 10_000
        for k, v in clean.items():
            if isinstance(v, str) and len(v) > max_str:
                clean[k] = v[:max_str] + "...[truncated]"

        # Cap total size
        max_bytes = self.config.max_share_size_kb * 1024
        if len(json.dumps(clean).encode()) > max_bytes:
            clean = {"_truncated": True, "_size": len(json.dumps(data).encode())}

        return clean

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Return node statistics."""
        return {
            "peer_id": self.peer_id,
            "enabled": self.config.enabled,
            "listening": self._server is not None,
            "port": self.config.port,
            "connected_peers": len(self.peers),
            "lookups_served": self.lookups_served,
            "lookups_received": self.lookups_received,
            "updates_received": self.updates_received,
        }
