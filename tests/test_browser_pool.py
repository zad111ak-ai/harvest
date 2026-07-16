"""
Tests for BrowserPool and its integration with Scraper.

Run: python3 -m pytest tests/test_browser_pool.py -v
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from harvest.browser_pool import BrowserPool, get_pool
from harvest.browser import BrowserSession


# ── Helper: create a mock BrowserSession ──


def _make_mock_session():
    """Create a mock BrowserSession that passes isinstance checks."""
    session = MagicMock(spec=BrowserSession)
    session.close = AsyncMock()
    return session


def _warm_pool(pool, *sessions):
    """Manually populate a pool's warm deque for testing."""
    pool._started = True
    for s in sessions:
        pool._warm.append(s)


# ── Tests ──


@pytest.fixture(autouse=True)
def _reset_global_pool():
    """Reset the global _pool singleton between tests."""
    import harvest.browser_pool as bp

    bp._pool = None
    yield
    bp._pool = None


class TestBrowserPoolCreation:
    """Test pool initialization and configuration."""

    def test_pool_default_config(self):
        """BrowserPool initializes with correct defaults."""
        pool = BrowserPool()
        assert pool.warm_count == 3
        assert pool.proxy is None
        assert pool.headless is True
        assert pool.solve_cloudflare is True
        assert pool._started is False
        assert len(pool._warm) == 0
        assert len(pool._active) == 0

    def test_pool_custom_config(self):
        """BrowserPool accepts custom configuration."""
        pool = BrowserPool(
            warm_count=5,
            proxy="http://proxy:8080",
            headless=False,
            solve_cloudflare=False,
            max_pages=10,
        )
        assert pool.warm_count == 5
        assert pool.proxy == "http://proxy:8080"
        assert pool.headless is False
        assert pool.solve_cloudflare is False
        assert pool.max_pages == 10

    def test_pool_stats_initialized(self):
        """Pool stats dict is initialized with zero counters."""
        pool = BrowserPool()
        expected_keys = {
            "total_requests",
            "pool_hits",
            "pool_misses",
            "total_wait_ms",
            "browsers_created",
            "browsers_reused",
        }
        assert set(pool.stats.keys()) == expected_keys
        assert all(v == 0 for v in pool.stats.values())


class TestBrowserPoolAcquireRelease:
    """Test acquire/release context manager."""

    @pytest.mark.asyncio
    async def test_acquire_yields_session(self):
        """acquire() context manager yields a browser session."""
        pool = BrowserPool(warm_count=1)
        mock_session = _make_mock_session()
        _warm_pool(pool, mock_session)

        async with pool.acquire() as browser:
            assert browser is mock_session
            assert mock_session in pool._active

        # After context exit, browser should be returned
        assert mock_session not in pool._active
        assert mock_session in pool._warm

    @pytest.mark.asyncio
    async def test_acquire_returns_to_pool(self):
        """After acquire context exits, browser returns to warm pool."""
        pool = BrowserPool(warm_count=2)
        s1, s2 = _make_mock_session(), _make_mock_session()
        _warm_pool(pool, s1, s2)

        assert len(pool._warm) == 2

        async with pool.acquire() as browser:
            assert browser is s1
            assert len(pool._warm) == 1
            assert len(pool._active) == 1

        # Released back
        assert len(pool._warm) == 2
        assert len(pool._active) == 0

    @pytest.mark.asyncio
    async def test_acquire_tracks_stats(self):
        """acquire() increments request and hit stats."""
        pool = BrowserPool(warm_count=1)
        mock_session = _make_mock_session()
        _warm_pool(pool, mock_session)

        async with pool.acquire():
            pass

        assert pool.stats["total_requests"] == 1
        assert pool.stats["pool_hits"] == 1
        assert pool.stats["pool_misses"] == 0

    @pytest.mark.asyncio
    async def test_acquire_miss_creates_new_browser(self):
        """When pool is empty, acquire creates a new browser (miss)."""
        pool = BrowserPool(warm_count=0)
        pool._started = True  # Mark as started even with 0 warm
        mock_session = _make_mock_session()

        with patch.object(pool, "_create_browser", return_value=mock_session):
            async with pool.acquire() as browser:
                assert browser is mock_session

        assert pool.stats["pool_misses"] == 1
        assert pool.stats["browsers_created"] == 1


class TestBrowserPoolStats:
    """Test pool statistics reporting."""

    def test_get_stats_before_start(self):
        """get_stats returns correct zero-state before start."""
        pool = BrowserPool()
        stats = pool.get_stats()
        assert stats["warm_available"] == 0
        assert stats["active"] == 0
        assert stats["hit_rate"] == "N/A"
        assert stats["avg_wait_ms"] == "N/A"

    @pytest.mark.asyncio
    async def test_get_stats_after_acquire_release(self):
        """get_stats reports correct values after usage."""
        pool = BrowserPool(warm_count=1)
        mock_session = _make_mock_session()
        _warm_pool(pool, mock_session)

        async with pool.acquire():
            pass

        stats = pool.get_stats()
        assert stats["total_requests"] == 1
        assert stats["pool_hits"] == 1
        assert stats["warm_available"] == 1
        assert stats["active"] == 0
        assert stats["hit_rate"] == "100.0%"

    @pytest.mark.asyncio
    async def test_get_stats_mixed_hits_and_misses(self):
        """Stats track hits and misses correctly."""
        pool = BrowserPool(warm_count=1)
        s1 = _make_mock_session()
        s2 = _make_mock_session()

        _warm_pool(pool, s1)

        with patch.object(pool, "_create_browser", return_value=s2):
            # First acquire: hit (from warm pool)
            async with pool.acquire():
                pass
            # Manually remove the session from warm pool to force a miss
            pool._warm.clear()
            # Second acquire: miss (pool empty, creates new)
            async with pool.acquire():
                pass

        stats = pool.get_stats()
        assert stats["total_requests"] == 2
        assert stats["pool_hits"] == 1
        assert stats["pool_misses"] == 1
        assert stats["hit_rate"] == "50.0%"


class TestBrowserPoolSingleton:
    """Test the global get_pool() singleton function."""

    @pytest.mark.asyncio
    async def test_get_pool_creates_once(self):
        """get_pool creates and returns a single global pool instance."""

        async def fake_start(self_pool):
            self_pool._started = True

        with patch.object(BrowserPool, "start", fake_start):
            pool1 = await get_pool(warm_count=1, headless=True)
            assert isinstance(pool1, BrowserPool)
            assert pool1._started is True

            pool2 = await get_pool(warm_count=5)  # kwargs ignored on reuse
            assert pool2 is pool1  # Same instance
            assert pool2.warm_count == 1  # Not overridden

    @pytest.mark.asyncio
    async def test_get_pool_reuses_existing(self):
        """Subsequent get_pool calls return the same pool."""
        with patch.object(BrowserPool, "start", new_callable=AsyncMock):
            p1 = await get_pool(warm_count=2)
            p2 = await get_pool()
            p3 = await get_pool(warm_count=10)
            assert p1 is p2 is p3

    @pytest.mark.asyncio
    async def test_reset_global_pool(self):
        """After resetting _pool, get_pool creates a new one."""
        import harvest.browser_pool as bp

        with patch.object(BrowserPool, "start", new_callable=AsyncMock):
            p1 = await get_pool(warm_count=2)
            bp._pool = None
            p2 = await get_pool(warm_count=4)
            assert p1 is not p2
            assert p2.warm_count == 4


class TestBrowserPoolWarmUp:
    """Test the warm_up method."""

    @pytest.mark.asyncio
    async def test_warm_up_fills_pool(self):
        """warm_up adds browsers up to the target count."""
        pool = BrowserPool(warm_count=3)
        s1, s2, s3 = _make_mock_session(), _make_mock_session(), _make_mock_session()
        _warm_pool(pool, s1, s2, s3)

        assert len(pool._warm) == 3

        # Remove one to make room, then warm_up to restore
        pool._warm.popleft()
        assert len(pool._warm) == 2

        s4 = _make_mock_session()
        with patch.object(pool, "_create_browser", return_value=s4):
            await pool.warm_up()

        assert len(pool._warm) == 3

    @pytest.mark.asyncio
    async def test_warm_up_skips_when_full(self):
        """warm_up does nothing when pool is already at target count."""
        pool = BrowserPool(warm_count=2)
        s1, s2 = _make_mock_session(), _make_mock_session()
        _warm_pool(pool, s1, s2)

        assert len(pool._warm) == 2

        with patch.object(pool, "_create_browser") as mock_create:
            await pool.warm_up()
            mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_warm_up_custom_count(self):
        """warm_up with a custom count fills to that count."""
        pool = BrowserPool(warm_count=1)
        s1 = _make_mock_session()
        _warm_pool(pool, s1)

        assert len(pool._warm) == 1

        # warm_up to 5: need 4 more
        new_sessions = [_make_mock_session() for _ in range(4)]
        call_count = 0

        def make_session():
            nonlocal call_count
            s = new_sessions[call_count]
            call_count += 1
            return s

        with patch.object(pool, "_create_browser", side_effect=make_session):
            await pool.warm_up(count=5)

        assert len(pool._warm) == 5


class TestBrowserPoolStop:
    """Test pool shutdown."""

    @pytest.mark.asyncio
    async def test_stop_closes_all_browsers(self):
        """stop() closes all warm and active browsers."""
        pool = BrowserPool(warm_count=2)
        s1 = _make_mock_session()
        s2 = _make_mock_session()
        _warm_pool(pool, s1, s2)

        assert len(pool._warm) == 2

        await pool.stop()
        assert len(pool._warm) == 0
        assert len(pool._active) == 0
        assert pool._started is False
        assert s1.close.called
        assert s2.close.called

    @pytest.mark.asyncio
    async def test_stop_idempotent(self):
        """Calling stop() twice doesn't raise."""
        pool = BrowserPool(warm_count=1)
        s1 = _make_mock_session()
        _warm_pool(pool, s1)

        await pool.stop()
        await pool.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_stop_closes_active_browsers(self):
        """stop() closes browsers currently in use (active)."""
        pool = BrowserPool(warm_count=0)
        pool._started = True
        s1 = _make_mock_session()
        pool._active.add(s1)

        await pool.stop()
        assert s1.close.called
        assert len(pool._active) == 0
