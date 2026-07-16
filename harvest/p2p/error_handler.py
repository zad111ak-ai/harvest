"""P2P Error Handler — graceful degradation for P2P operations.

If P2P fails, Harvest continues working locally. No crashes, no data loss.
"""

from __future__ import annotations

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger("harvest.p2p.errors")


def p2p_fallback(fallback_value: Any = None) -> Callable:
    """Decorator: if P2P operation fails, return fallback value silently."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.debug(f"P2P fallback ({func.__name__}): {e}")
                return fallback_value

        return wrapper

    return decorator


class P2PErrorHandler:
    """Track P2P errors and auto-disable when too many fail."""

    def __init__(self, max_errors: int = 10, cooldown_sec: int = 300) -> None:
        self._error_count = 0
        self._max_errors = max_errors
        self._cooldown_sec = cooldown_sec
        self._disabled = False
        self._reenable_task: Optional[asyncio.Task] = None

    def should_try(self) -> bool:
        """Check if we should attempt a P2P operation."""
        return not self._disabled

    def record_success(self) -> None:
        """Reset error counter on success."""
        self._error_count = 0

    def record_error(self) -> None:
        """Increment error count; auto-disable if threshold reached."""
        self._error_count += 1
        if self._error_count >= self._max_errors and not self._disabled:
            logger.warning(f"P2P disabled after {self._error_count} consecutive errors, cooldown {self._cooldown_sec}s")
            self._disabled = True
            try:
                loop = asyncio.get_running_loop()
                self._reenable_task = loop.create_task(self._re_enable())
            except RuntimeError:
                pass  # No event loop running

    async def _re_enable(self) -> None:
        """Re-enable P2P after cooldown."""
        await asyncio.sleep(self._cooldown_sec)
        self._disabled = False
        self._error_count = 0
        logger.info("P2P re-enabled after cooldown")

    @property
    def is_disabled(self) -> bool:
        return self._disabled
