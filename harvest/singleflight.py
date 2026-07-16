"""Singleflight — Deduplicate concurrent identical requests.

Ensures only one in-flight request per key. If N callers request the
same key simultaneously, only 1 makes the actual call and the rest
wait and receive the same result (or error).

Usage:
    sf = Singleflight()

    # Pattern 1 — Context manager with leader flag
    async with sf.do("https://example.com") as is_leader:
        if is_leader:
            result = await fetch("https://example.com")

    # Pattern 2 — Decorator (first arg = dedup key)
    @sf.do_serialize
    async def fetch_page(url: str) -> dict:
        return await aiohttp.get(url)

    # Pattern 3 — Go-style: pass callable + args
    result = await sf.call("https://example.com", fetch, "https://example.com")
"""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


class Singleflight:
    """Coalesces concurrent calls for the same key into one execution.

    Internally maintains a dict mapping key → Future.  The first caller
    for a given key creates the Future and runs the actual coroutine.
    Subsequent callers for the same key await that *same* Future and
    receive the identical result or error.
    """

    def __init__(self) -> None:
        self._inflight: dict[str, asyncio.Future[Any]] = {}

    # -- Context-manager interface (primary) --------------------------------

    def do(self, key: str) -> _DoContext:
        """Context manager that coalesces calls for *key*.

        The ``as`` variable is ``True`` for the leader (first caller) and
        ``False`` for followers.  Followers that enter the body should
        ``return`` early.  Errors raised by the leader propagate to all
        followers via the shared Future::

            async with sf.do(url) as is_leader:
                if is_leader:
                    result = await fetch(url)
        """
        return _DoContext(self, key)

    # -- Go-style: pass callable --------------------------------------------

    async def call(
        self,
        key: str,
        fn: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Call *fn* once for *key*, coalescing concurrent callers."""
        is_leader, future = self._acquire(key)
        try:
            if is_leader:
                result = await fn(*args, **kwargs)
                future.set_result(result)
            else:
                result = await asyncio.shield(future)
            return result
        except BaseException as exc:
            if is_leader and not future.done():
                future.set_exception(exc)
            raise
        finally:
            if is_leader:
                self._release(key)

    # -- Decorator interface -------------------------------------------------

    def do_serialize(
        self,
        fn: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        """Decorator that serializes calls through the singleflight.

        The *first* positional argument of the wrapped function is
        treated as the deduplication key::

            @sf.do_serialize
            async def fetch_page(url: str) -> dict:
                return await aiohttp.get(url)
        """

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            key = str(args[0]) if args else kwargs.get("key", fn.__name__)
            return await self.call(key, fn, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    # -- Internal helpers ----------------------------------------------------

    def _acquire(self, key: str) -> tuple[bool, asyncio.Future[Any]]:
        """Return *(is_leader, future)* for *key*."""
        if key in self._inflight:
            return False, self._inflight[key]

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._inflight[key] = fut
        return True, fut

    def _release(self, key: str) -> None:
        """Remove *key* from the in-flight map."""
        self._inflight.pop(key, None)

    @property
    def inflight_count(self) -> int:
        """Number of currently coalesced keys."""
        return len(self._inflight)


class _DoContext:
    """Async context manager returned by :meth:`Singleflight.do`.

    The ``as`` variable is ``True`` for the leader (first caller) and
    ``False`` for followers.  Followers that enter the body should
    ``return`` early.  Errors raised by the leader propagate to all
    followers via the shared Future.
    """

    def __init__(self, sf: Singleflight, key: str) -> None:
        self._sf = sf
        self._key = key
        self._is_leader = False
        self._future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()

    async def __aenter__(self) -> bool:
        self._is_leader, self._future = self._sf._acquire(self._key)
        return self._is_leader

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        if self._is_leader:
            if exc_val is not None:
                # Leader raised — propagate to all waiters.
                if not self._future.done():
                    self._future.set_exception(exc_val)
            elif not self._future.done():
                # Leader succeeded without error — resolve the future.
                self._future.set_result(True)
            # Only leader releases — followers must NOT remove the key
            # while the leader's future is still in-flight.
            self._sf._release(self._key)
        # Don't suppress exceptions — let them propagate naturally.
        return False
