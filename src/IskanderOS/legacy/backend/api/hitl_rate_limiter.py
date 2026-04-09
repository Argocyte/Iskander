"""
hitl_rate_limiter.py — Per-role rate limiter for HITL-triggering endpoints (Fix 6).

Sliding window rate limiter that prevents DoS via excessive HITL approval requests.
Includes Crisis Mode: rate limits expand 100x when EmergencyVeto or CircuitBreaker active.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)

CRISIS_MULTIPLIER = 100


class HITLRateLimiter:
    """Sliding window rate limiter for HITL-triggering endpoints.

    Singleton: obtain via ``HITLRateLimiter.get_instance()``.
    """

    _instance: HITLRateLimiter | None = None

    def __init__(self) -> None:
        # key: (user_address, endpoint) -> list of timestamps
        self._requests: dict[tuple[str, str], list[float]] = defaultdict(list)

    @classmethod
    def get_instance(cls) -> HITLRateLimiter:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Test-only: tear down singleton."""
        cls._instance = None

    async def check(self, user_address: str, endpoint: str) -> None:
        """Check rate limit. Raises HTTP 429 if exceeded."""
        from backend.config import settings

        limit = getattr(settings, 'hitl_max_requests_per_hour', 10)

        # Crisis mode expansion
        if await self._is_crisis_mode_active():
            crisis_mult = getattr(settings, 'hitl_crisis_multiplier', CRISIS_MULTIPLIER)
            limit *= crisis_mult
            logger.warning("HITL crisis mode active — rate limit expanded to %d/hour", limit)

        key = (user_address, endpoint)
        now = time.time()
        window = 3600  # 1 hour

        # Prune old entries
        self._requests[key] = [
            t for t in self._requests[key] if now - t < window
        ]

        recent = len(self._requests[key])
        if recent >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"HITL rate limit exceeded: {recent}/{limit} per hour for {endpoint}"
            )

        # Record this request
        self._requests[key].append(now)

    async def _is_crisis_mode_active(self) -> bool:
        """Check if EmergencyVeto is filed or CircuitBreaker is tripped.

        STUB: In production, check:
        - veto_records for any status='filed' in last 24 hours
        - solvency_snapshots for circuit_breaker_active=True
        - energy_events for level='RED' in last hour
        """
        return False


async def hitl_rate_check(user_address: str, endpoint: str) -> None:
    """Convenience function for use in FastAPI Depends()."""
    await HITLRateLimiter.get_instance().check(user_address, endpoint)
