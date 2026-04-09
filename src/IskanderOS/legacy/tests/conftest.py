# tests/conftest.py
"""Shared pytest fixtures for Iskander OS tests."""
from __future__ import annotations
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock

from backend.main import app


# pytest-asyncio >= 0.21 with asyncio_mode = auto creates a fresh event loop
# per test function by default — no session-scoped event_loop override needed.
# If session-scoped async fixtures are added in future, revisit this decision.
@pytest_asyncio.fixture
async def async_client():
    """HTTP test client backed by the FastAPI app (no real DB)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def mock_db():
    """asyncpg connection mock — override get_db with this in individual tests."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    conn.fetchval = AsyncMock(return_value=None)
    return conn
