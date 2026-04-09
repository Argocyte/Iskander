"""
Pytest fixtures for steward-data tests.

Uses an in-memory SQLite database so tests run without PostgreSQL.
SQLite doesn't support INTERVAL arithmetic, so endpoints that use it
are tested via mocking; the conftest provides the DB session fixture
for endpoints that use simpler queries.
"""
import os
import sys

# Make 'main' importable from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-token")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app, get_db

_SQLITE_URL = "sqlite:///:memory:"


def _build_engine():
    # StaticPool: all connections (including across threads) share one in-memory DB.
    # Without it, each new connection gets a fresh empty database and the tables
    # created in _build_engine() are invisible to the TestClient's session.
    engine = create_engine(
        _SQLITE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ledger_accounts (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                balance REAL NOT NULL DEFAULT 0,
                currency TEXT NOT NULL DEFAULT 'GBP',
                updated_at TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS financial_transactions (
                id INTEGER PRIMARY KEY,
                transaction_date TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                direction TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS financial_year_budget (
                financial_year TEXT PRIMARY KEY,
                budget_income REAL,
                budget_expenditure REAL,
                created_at TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS compliance_deadlines (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                due_date TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                consequence TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'upcoming',
                created_at TEXT
            )
        """))
        conn.commit()
    return engine


@pytest.fixture()
def db_engine():
    return _build_engine()


@pytest.fixture()
def client(db_engine):
    """TestClient with the in-memory DB injected via dependency override."""
    TestSession = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def authed_headers():
    return {"Authorization": "Bearer test-token"}
