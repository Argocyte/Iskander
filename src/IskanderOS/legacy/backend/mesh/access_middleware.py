"""
access_middleware.py — gSBT access-control decorator (Phase 25).

``@requires_access(token_type='steward')`` validates the requester's gSBT
balance via the CoopIdentity contract before allowing IPFS reads.

STUB NOTICE:
  In development the decorator always allows access (with a logged warning).
  In production it would call ``CoopIdentity.balanceOf(requester)`` via web3
  and raise ``AccessDenied`` if the requester lacks the required token type.
"""
from __future__ import annotations

import asyncio
import functools
import logging
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# ── Exception ────────────────────────────────────────────────────────────────


@dataclass
class AccessDenied(Exception):
    """Raised when a requester lacks the required gSBT token type."""

    token_type: str
    requester: str
    message: str = ""

    def __post_init__(self) -> None:
        self.message = (
            self.message
            or f"Access denied: requester '{self.requester}' does not hold "
            f"a gSBT of type '{self.token_type}'."
        )
        super().__init__(self.message)


# ── Decorator ────────────────────────────────────────────────────────────────


def requires_access(token_type: str = "steward") -> Callable[[F], F]:
    """Decorator that gates a function behind gSBT ownership verification.

    Works with both sync and async callables.

    Parameters
    ----------
    token_type:
        The gSBT token type the requester must hold (e.g. ``"steward"``,
        ``"worker-owner"``).

    STUB:
        Always allows access in development and logs a warning.
        In production, replace ``_check_access_stub`` with a web3 call to
        ``CoopIdentity.balanceOf(requester)``.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            requester = kwargs.get("requester", "unknown")
            _check_access_stub(token_type, requester)
            return await fn(*args, **kwargs)

        @functools.wraps(fn)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            requester = kwargs.get("requester", "unknown")
            _check_access_stub(token_type, requester)
            return fn(*args, **kwargs)

        if asyncio.iscoroutinefunction(fn):
            return _async_wrapper  # type: ignore[return-value]
        return _sync_wrapper  # type: ignore[return-value]

    return decorator  # type: ignore[return-value]


# ── Stub Implementation ─────────────────────────────────────────────────────


def _check_access_stub(token_type: str, requester: str) -> None:
    """STUB: always allows access; logs a warning.

    In production, this would:
      1. Resolve requester → Ethereum address.
      2. Call ``CoopIdentity.balanceOf(address)`` via web3.
      3. Raise ``AccessDenied`` if balance is zero for the requested token type.
    """
    logger.warning(
        "ACCESS CHECK STUBBED — allowing %s access for requester '%s'. "
        "In production this would verify gSBT ownership on-chain.",
        token_type,
        requester,
    )
