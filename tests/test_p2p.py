"""Tests for P2P cache network."""

from __future__ import annotations

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
