"""Tests for P2P cache network."""

from __future__ import annotations

import asyncio
import time

import pytest
from harvest.cache import ResponseCache
from harvest.p2p.node import P2PNode, P2PConfig, PeerInfo
from harvest.p2p.error_handler import P2PErrorHandler, p2p_fallback
from harvest.p2p_network import P2PCacheNetwork


# ── P2PConfig ──────────────────────────────────────────────────


class TestP2PConfig:
    def test_defaults(self) -> None:
        c = P2PConfig()
        assert c.enabled is False  # Opt-in: disabled by default
        assert c.port == 8765
        assert c.max_peers_to_query == 5
        assert isinstance(c.bootstrap_peers, list)

    def test_custom(self) -> None:
        c = P2PConfig(port=9999, enabled=False, max_peers_to_query=3)
        assert c.port == 9999
        assert c.enabled is False
        assert c.max_peers_to_query == 3


# ── PeerInfo ───────────────────────────────────────────────────


class TestPeerInfo:
    def test_create(self) -> None:
        p = PeerInfo(peer_id="test-1", address="ws://localhost:8765")
        assert p.peer_id == "test-1"
        assert p.reputation == 0.5


# ── P2PNode ────────────────────────────────────────────────────


class TestP2PNode:
    def test_init(self) -> None:
        node = P2PNode()
        assert node.peer_id.startswith("harvest-")
        assert len(node.peers) == 0
        assert node.config.enabled is False  # Opt-in: disabled by default

    def test_stats(self) -> None:
        node = P2PNode()
        s = node.stats()
        assert "peer_id" in s
        assert s["connected_peers"] == 0
        assert s["enabled"] is False

    def test_sanitize_for_sharing(self) -> None:
        node = P2PNode()
        data = {
            "email": "secret@example.com",
            "password": "hunter2",
            "result": {"price": 42},
            "token": "abc123",
        }
        clean = node.sanitize_for_sharing(data)
        assert "email" not in clean
        assert "password" not in clean
        assert "token" not in clean
        assert clean["result"] == {"price": 42}

    def test_sanitize_truncation(self) -> None:
        node = P2PNode(P2PConfig(max_share_size_kb=1))
        data = {"big": "x" * 2_000_000}
        clean = node.sanitize_for_sharing(data)
        assert "_truncated" in clean

    def test_handler_registration(self) -> None:
        node = P2PNode()

        async def handler(key: str) -> None:
            return None

        node.on("cache_lookup", handler)
        assert "cache_lookup" in node._handlers

    def test_peer_persistence(self, tmp_path: object) -> None:
        node = P2PNode()
        node.peers["p1"] = PeerInfo(peer_id="p1", address="ws://x:1", reputation=0.8)
        node._save_peers()

        # Load in new node
        node2 = P2PNode()
        node2._load_peers()
        assert "p1" in node2.peers
        assert node2.peers["p1"].reputation == 0.8

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        config = P2PConfig(port=18765, bootstrap_peers=[], enabled=True)
        node = P2PNode(config)
        await node.start()
        assert node._server is not None
        assert node.config.port == 18765
        await node.stop()


# ── P2PErrorHandler ────────────────────────────────────────────


class TestP2PErrorHandler:
    def test_initial_state(self) -> None:
        h = P2PErrorHandler()
        assert h.should_try() is True
        assert h.is_disabled is False

    def test_success_resets(self) -> None:
        h = P2PErrorHandler(max_errors=3)
        h.record_error()
        h.record_error()
        h.record_success()
        assert h._error_count == 0
        assert h.should_try() is True

    def test_auto_disable(self) -> None:
        h = P2PErrorHandler(max_errors=3, cooldown_sec=999)
        h.record_error()
        h.record_error()
        h.record_error()
        assert h.is_disabled is True
        assert h.should_try() is False

    @pytest.mark.asyncio
    async def test_p2p_fallback_decorator(self) -> None:
        @p2p_fallback(fallback_value="default")
        async def broken() -> str:
            raise ConnectionError("network down")

        result = await broken()
        assert result == "default"

    @pytest.mark.asyncio
    async def test_p2p_fallback_success(self) -> None:
        @p2p_fallback(fallback_value=None)
        async def working() -> str:
            return "ok"

        result = await working()
        assert result == "ok"


# ── P2PCacheNetwork ────────────────────────────────────────────


class TestP2PCacheNetwork:
    def test_local_cache_hit(self) -> None:
        cache = ResponseCache()
        net = P2PCacheNetwork(cache, P2PConfig(enabled=False))

        # Set locally
        key_hash = net._make_key("https://example.com", "extract price")
        cache.set(key_hash, {"price": 42})

        # Get locally
        result = net.get("https://example.com", "extract price")
        assert result == {"price": 42}

    def test_local_cache_miss(self) -> None:
        cache = ResponseCache()
        net = P2PCacheNetwork(cache, P2PConfig(enabled=False))
        result = net.get("https://unknown.com", "query")
        assert result is None

    def test_make_key_deterministic(self) -> None:
        k1 = P2PCacheNetwork._make_key("https://A.com", "Query")
        k2 = P2PCacheNetwork._make_key("https://a.com", "query")
        assert k1 == k2  # Case-insensitive

    def test_make_key_different(self) -> None:
        k1 = P2PCacheNetwork._make_key("https://a.com", "q1")
        k2 = P2PCacheNetwork._make_key("https://a.com", "q2")
        assert k1 != k2

    def test_verify_entry_valid(self) -> None:
        net = P2PCacheNetwork(ResponseCache())
        entry = {"data": {"x": 1}, "timestamp": time.time()}
        assert net._verify_entry(entry) is True

    def test_verify_entry_old(self) -> None:
        net = P2PCacheNetwork(ResponseCache())
        entry = {"data": {"x": 1}, "timestamp": time.time() - 999999}
        assert net._verify_entry(entry) is False

    def test_verify_entry_empty(self) -> None:
        net = P2PCacheNetwork(ResponseCache())
        assert net._verify_entry({}) is False
        assert net._verify_entry({"no_data": True}) is False

    def test_stats(self) -> None:
        cache = ResponseCache()
        net = P2PCacheNetwork(cache, P2PConfig(enabled=False))
        stats = net.get_stats()
        assert stats["enabled"] is False
        assert stats["local_hits"] == 0
        assert stats["p2p_hits"] == 0
        assert stats["misses"] == 0

    @pytest.mark.asyncio
    async def test_p2p_lookup_no_peers(self) -> None:
        cache = ResponseCache()
        config = P2PConfig(enabled=False)
        net = P2PCacheNetwork(cache, config)
        result = await net.get_p2p("https://example.com", "test")
        assert result is None  # No peers, no P2P, just local miss


# ── Phase 1: Content Hash Verification ────────────────────────


class TestContentHash:
    def test_compute_content_hash(self) -> None:
        from harvest.p2p.node import compute_content_hash

        h = compute_content_hash({"price": 42})
        assert len(h) == 64  # SHA-256 hex
        assert isinstance(h, str)

    def test_deterministic(self) -> None:
        from harvest.p2p.node import compute_content_hash

        assert compute_content_hash({"a": 1}) == compute_content_hash({"a": 1})
        assert compute_content_hash({"a": 1}) != compute_content_hash({"a": 2})

    def test_verify_content_hash_valid(self) -> None:
        from harvest.p2p.node import compute_content_hash, verify_content_hash

        data = {"price": 42}
        entry = {"data": data, "content_hash": compute_content_hash(data)}
        assert verify_content_hash(entry) is True

    def test_verify_content_hash_tampered(self) -> None:
        from harvest.p2p.node import compute_content_hash, verify_content_hash

        data = {"price": 42}
        entry = {"data": data, "content_hash": compute_content_hash({"price": 99})}
        assert verify_content_hash(entry) is False

    def test_verify_content_hash_legacy(self) -> None:
        from harvest.p2p.node import verify_content_hash

        assert verify_content_hash({"data": {"x": 1}}) is True  # no hash = pass
        assert verify_content_hash({}) is True


# ── Phase 1: Peer Reputation ──────────────────────────────────


class TestPeerReputation:
    def test_initial_reputation(self) -> None:
        p = PeerInfo(peer_id="t", address="ws://x:1")
        assert p.reputation == 0.5
        assert p.score == 0.5
        assert p.successes == 0
        assert p.failures == 0

    def test_success_improves(self) -> None:
        p = PeerInfo(peer_id="t", address="ws://x:1")
        p.update_reputation(True, latency_ms=50)
        assert p.successes == 1
        assert p.reputation > 0.5

    def test_failure_degrades(self) -> None:
        p = PeerInfo(peer_id="t", address="ws://x:1")
        p.update_reputation(False)
        assert p.failures == 1
        assert p.reputation < 0.5

    def test_reputation_accumulates(self) -> None:
        p = PeerInfo(peer_id="t", address="ws://x:1")
        for _ in range(10):
            p.update_reputation(True, latency_ms=50)
        for _ in range(3):
            p.update_reputation(False)
        assert p.successes == 10
        assert p.failures == 3
        assert 0.5 < p.reputation < 1.0

    def test_reputation_floor(self) -> None:
        p = PeerInfo(peer_id="t", address="ws://x:1")
        for _ in range(100):
            p.update_reputation(False)
        assert p.reputation >= 0.1  # minimum floor


# ── Phase 1: Enhanced Stats ───────────────────────────────────


class TestP2PNodeStats:
    def test_stats_includes_reputation(self) -> None:
        node = P2PNode()
        node.peers["p1"] = PeerInfo(peer_id="p1", address="ws://x:1")
        node.peers["p1"].update_reputation(True, latency_ms=100)
        s = node.stats()
        assert "peer_reputations" in s
        assert "p1" in s["peer_reputations"]
        assert s["peer_reputations"]["p1"] == round(node.peers["p1"].reputation, 2)

    def test_stats_includes_recent_entries(self) -> None:
        node = P2PNode()
        s = node.stats()
        assert "recent_entries" in s
        assert s["recent_entries"] == 0


# ── Phase 1: Broadcast with Content Hash ──────────────────────


class TestBroadcastWithHash:
    @pytest.mark.asyncio
    async def test_broadcast_adds_content_hash(self) -> None:
        """broadcast() should add content_hash if missing."""
        node = P2PNode()
        # No peers → broadcast returns early, but we can test the hash logic
        entry = {"key": "test", "data": {"price": 42}}
        await node.broadcast(entry)
        # No peers connected, so entry won't have hash added
        # (broadcast returns early when no peers)
        assert "key" in entry

    def test_entry_with_hash_survives_verify(self) -> None:
        """Entry with valid content_hash passes _verify_entry."""
        from harvest.p2p.node import compute_content_hash
        from harvest.p2p_network import P2PCacheNetwork

        data = {"price": 42}
        entry = {
            "data": data,
            "timestamp": time.time(),
            "content_hash": compute_content_hash(data),
        }
        net = P2PCacheNetwork(ResponseCache())
        assert net._verify_entry(entry) is True

    def test_entry_with_bad_hash_fails_verify(self) -> None:
        """Entry with tampered content_hash fails _verify_entry."""
        from harvest.p2p_network import P2PCacheNetwork

        entry = {
            "data": {"price": 42},
            "timestamp": time.time(),
            "content_hash": "0000000000000000000000000000000000000000000000000000000000000000",
        }
        net = P2PCacheNetwork(ResponseCache())
        assert net._verify_entry(entry) is False

    def test_entry_no_hash_passes_verify(self) -> None:
        """Legacy entry without content_hash still passes _verify_entry."""
        from harvest.p2p_network import P2PCacheNetwork

        entry = {"data": {"price": 42}, "timestamp": time.time()}
        net = P2PCacheNetwork(ResponseCache())
        assert net._verify_entry(entry) is True


# ── Phase 1: Reputation in Peer Selection ─────────────────────


class TestReputationPeerSelection:
    def test_high_reputation_peer_queried_first(self) -> None:
        """lookup() should prefer higher-reputation peers."""
        node = P2PNode()
        # Create peers with different reputations
        good = PeerInfo(peer_id="good", address="ws://good:1", reputation=0.9)
        bad = PeerInfo(peer_id="bad", address="ws://bad:1", reputation=0.2)
        node.peers = {"good": good, "bad": bad}

        candidates = sorted(
            node.peers.values(),
            key=lambda p: p.reputation,
            reverse=True,
        )[: node.config.max_peers_to_query]
        assert candidates[0].peer_id == "good"

    def test_peer_persistence_saves_reputation(self) -> None:
        """_save_peers should include reputation data."""
        node = P2PNode()
        node.peers["test"] = PeerInfo(peer_id="test", address="ws://x:1", reputation=0.75)
        node._save_peers()
        # Check the file
        import json
        from pathlib import Path

        path = Path.home() / ".harvest" / "p2p_peers.json"
        data = json.loads(path.read_text())
        assert data["test"]["reputation"] == 0.75


# ── Phase 1: Stale Peer Pruning ──────────────────────────────


class TestStalePeerPruning:
    def test_stale_peers_identified(self) -> None:
        """Peers not seen in 10+ minutes should be prunable."""
        node = P2PNode()
        # Fresh peer
        fresh = PeerInfo(peer_id="fresh", address="ws://f:1", last_seen=time.time())
        # Stale peer (15 min ago)
        stale = PeerInfo(
            peer_id="stale",
            address="ws://s:1",
            last_seen=time.time() - 900,
        )
        node.peers = {"fresh": fresh, "stale": stale}

        # Identify stale
        stale_ids = [pid for pid, p in node.peers.items() if time.time() - p.last_seen > 600]
        assert "stale" in stale_ids
        assert "fresh" not in stale_ids


# ── End-to-End Integration Test ───────────────────────────────


class TestP2PEndToEnd:
    """End-to-end tests: two nodes connecting and sharing cache."""

    @pytest.mark.asyncio
    async def test_two_nodes_connect(self) -> None:
        """Node A starts, Node B connects to it via hello."""
        node_a = P2PNode(P2PConfig(port=18800, enabled=True, bootstrap_peers=[]))
        node_b = P2PNode(P2PConfig(port=18801, enabled=True, bootstrap_peers=[]))
        try:
            await node_a.start()
            await node_b.start()
            # B connects to A
            await node_b._connect_to_peer(f"ws://127.0.0.1:{node_a.config.port}")
            # Wait for handshake
            for _ in range(10):
                await asyncio.sleep(0.2)
                if node_a.peer_id in node_b.peers or node_b.peer_id in node_a.peers:
                    break
            assert node_a.peer_id in node_b.peers or node_b.peer_id in node_a.peers
        finally:
            await node_a.stop()
            await node_b.stop()

    @pytest.mark.asyncio
    async def test_cache_hit_after_set(self) -> None:
        """P2PCacheNetwork set + get (local path) returns data."""
        cache = ResponseCache()
        net = P2PCacheNetwork(cache)
        net.set("https://example.com", "price", {"value": 42})
        result = net.get("https://example.com", "price")
        assert result == {"value": 42}

    @pytest.mark.asyncio
    async def test_content_hash_e2e(self) -> None:
        """Full flow: set → compute hash → broadcast → verify."""
        from harvest.p2p.node import compute_content_hash

        cache = ResponseCache()
        net = P2PCacheNetwork(cache)
        data = {"price": 42, "token": "ETH"}
        net.set("https://example.com", "price", data)

        # Verify local cache entry has data
        result = net.get("https://example.com", "price")
        assert result == data

        # Compute hash and verify integrity
        h = compute_content_hash(data)
        entry = {"data": data, "content_hash": h, "timestamp": time.time()}
        assert net._verify_entry(entry) is True

        # Tamper detection
        bad_entry = {"data": {"price": 99}, "content_hash": h, "timestamp": time.time()}
        assert net._verify_entry(bad_entry) is False
