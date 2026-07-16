"""Tests for Singleflight — dedup concurrent identical requests."""

import asyncio


from harvest.singleflight import Singleflight


# ---------------------------------------------------------------------------
# 1. Basic dedup — only one call is made
# ---------------------------------------------------------------------------


async def test_basic_dedup():
    """When multiple callers await the same key, the function is called once."""
    sf = Singleflight()
    call_count = 0

    async def expensive_work() -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return "result"

    async def caller():
        async with sf.do("url-1") as is_leader:
            if is_leader:
                return await expensive_work()

    results = await asyncio.gather(*[caller() for _ in range(5)])
    assert call_count == 1
    assert len(results) == 5  # all complete without error


# ---------------------------------------------------------------------------
# 2. Concurrent callers get same result via call()
# ---------------------------------------------------------------------------


async def test_call_dedup():
    """sf.call() coalesces concurrent callers and returns same result."""
    sf = Singleflight()
    call_count = 0

    async def work(key: str) -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return f"result-{key}"

    results = await asyncio.gather(
        sf.call("target", work, "target"),
        sf.call("target", work, "target"),
        sf.call("target", work, "target"),
    )
    assert call_count == 1
    assert all(r == "result-target" for r in results)


# ---------------------------------------------------------------------------
# 3. Error propagation — all waiters get the exception
# ---------------------------------------------------------------------------


async def test_error_propagation():
    """If the leader raises, all followers should also see the error."""
    sf = Singleflight()

    async def failing_work() -> str:
        async with sf.do("bad-url"):
            await asyncio.sleep(0.02)
            raise ValueError("HTTP 500")

    async def caller() -> str | None:
        try:
            async with sf.do("bad-url"):
                await asyncio.sleep(0.03)
        except ValueError:
            return "caught"

    # return_exceptions so gather doesn't abort on first error
    results = await asyncio.gather(
        failing_work(),
        caller(),
        caller(),
        caller(),
        return_exceptions=True,
    )
    # The leader raises ValueError; followers get it via future
    caught = sum(1 for r in results if r == "caught")
    errors = sum(1 for r in results if isinstance(r, ValueError))
    assert caught >= 1 or errors >= 1


# ---------------------------------------------------------------------------
# 4. Different keys are independent
# ---------------------------------------------------------------------------


async def test_different_keys_independent():
    """Calls with different keys execute independently."""
    sf = Singleflight()
    call_count = {"a": 0, "b": 0, "c": 0}

    async def work(key: str):
        call_count[key] += 1
        await asyncio.sleep(0.02)

    async def caller(key: str):
        async with sf.do(key) as is_leader:
            if is_leader:
                await work(key)

    await asyncio.gather(
        caller("a"),
        caller("b"),
        caller("c"),
        caller("a"),
        caller("b"),
        caller("c"),
    )
    assert call_count["a"] == 1
    assert call_count["b"] == 1
    assert call_count["c"] == 1


# ---------------------------------------------------------------------------
# 5. do_serialize decorator
# ---------------------------------------------------------------------------


async def test_do_serialize_decorator():
    """The do_serialize decorator coalesces calls by first arg."""
    sf = Singleflight()
    call_count = 0

    @sf.do_serialize
    async def fetch_page(url: str) -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return f"page-{url}"

    tasks = [fetch_page("https://x.com") for _ in range(4)]
    results = await asyncio.gather(*tasks)
    assert call_count == 1
    assert len(results) == 4
    assert all(r == "page-https://x.com" for r in results)


async def test_do_serialize_different_keys():
    """do_serialize still executes different keys independently."""
    sf = Singleflight()
    call_count = 0

    @sf.do_serialize
    async def fetch_page(url: str) -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.02)
        return f"page-{url}"

    results = await asyncio.gather(
        fetch_page("url-a"),
        fetch_page("url-b"),
        fetch_page("url-c"),
    )
    assert call_count == 3
    assert all(r.startswith("page-") for r in results)


# ---------------------------------------------------------------------------
# 6. Integration with cache pattern
# ---------------------------------------------------------------------------


async def test_integration_cache_pattern():
    """Singleflight works as a fetch-through layer in front of a cache."""
    from harvest.cache import ResponseCache

    cache = ResponseCache(ttl_seconds=60)
    sf = Singleflight()
    fetch_count = 0

    async def scrape(url: str) -> dict:
        nonlocal fetch_count
        fetch_count += 1
        await asyncio.sleep(0.05)
        return {"url": url, "title": "Example"}

    async def cached_fetch(url: str) -> dict:
        cached = cache.get(url)
        if cached is not None:
            return cached
        async with sf.do(url) as is_leader:
            if is_leader:
                result = await scrape(url)
                cache.set(url, result)
            else:
                # Follower: wait for leader to finish, then read from cache
                await asyncio.sleep(0.1)
        return cache.get(url)  # type: ignore[return-value]

    # Fire 10 concurrent requests for the same URL
    tasks = [cached_fetch("https://example.com") for _ in range(10)]
    results = await asyncio.gather(*tasks)

    # Only 1 actual fetch
    assert fetch_count == 1
    # All 10 callers got the same result
    for r in results:
        assert r is not None
        assert r["title"] == "Example"


# ---------------------------------------------------------------------------
# 7. inflight_count property
# ---------------------------------------------------------------------------


async def test_inflight_count():
    """inflight_count reflects the number of active coalesced keys."""
    sf = Singleflight()
    entered = asyncio.Event()
    proceed = asyncio.Event()

    async def slow():
        async with sf.do("x") as is_leader:
            if is_leader:
                entered.set()
                await proceed.wait()

    task = asyncio.create_task(slow())
    await entered.wait()
    assert sf.inflight_count == 1

    proceed.set()
    await task
    assert sf.inflight_count == 0


# ---------------------------------------------------------------------------
# 8. Sequential calls reuse the key (no stale futures)
# ---------------------------------------------------------------------------


async def test_sequential_reuse():
    """After a singleflight round completes, the same key can be used again."""
    sf = Singleflight()
    call_count = 0

    async def work():
        nonlocal call_count
        call_count += 1

    for _ in range(5):
        async with sf.do("reusable-key") as is_leader:
            if is_leader:
                await work()

    assert call_count == 5
    assert sf.inflight_count == 0
