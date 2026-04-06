# backend/db.py
"""
db.py — asyncpg connection pool for Iskander OS.

This is the first module in the codebase to provide real PostgreSQL
persistence (other routers still use in-memory stubs pending migration).

Usage in FastAPI endpoints:
    from backend.db import get_db
    import asyncpg

    @router.get("/example")
    async def example(conn: asyncpg.Connection = Depends(get_db)):
        rows = await conn.fetch("SELECT id FROM deliberation_threads")
        return [dict(r) for r in rows]
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

import asyncpg
from fastapi import HTTPException

from backend.config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the singleton asyncpg connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        # settings.database_url uses SQLAlchemy format: postgresql+asyncpg://...
        # Strip the driver prefix for raw asyncpg
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        try:
            _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
            logger.info("asyncpg pool initialised: %s", dsn.split("@")[-1])
        except Exception as exc:
            logger.error("Failed to create asyncpg pool: %s", exc)
            raise
    return _pool


async def close_pool() -> None:
    """Gracefully close the pool on application shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    FastAPI dependency: yields a single connection from the pool.

    Usage:
        @router.post("/threads")
        async def create_thread(conn = Depends(get_db)):
            ...
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn
