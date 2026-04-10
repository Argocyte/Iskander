"""
Tests for S3 auth hardening on tension endpoints (issue #56).

Covers four security fixes:
  1. log_tension:    X-Actor-User-Id must match logged_by if header present
  2. list_tensions:  scoped to actor when X-Actor-User-Id header present
  3. update_tension: X-Actor-User-Id must match updated_by if header present
  4. set_review_date: review_date must be a future date
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Environment bootstrap — before any service module is imported
# ---------------------------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("LOOMIO_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "")

# Stub ipfs.pin_json before main.py is imported (conftest adds service dir to path)
import ipfs as _ipfs  # noqa: E402
_ipfs.pin_json = MagicMock(return_value="QmTestCID")  # type: ignore[attr-defined]

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import main as app_module  # noqa: E402
from db import Base, Decision as DecisionModel, get_db  # noqa: E402

# ---------------------------------------------------------------------------
# In-memory SQLite DB
# ---------------------------------------------------------------------------

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(TEST_ENGINE)
    Base.metadata.create_all(TEST_ENGINE)
    app_module.app.dependency_overrides[get_db] = override_get_db
    yield
    app_module.app.dependency_overrides.clear()


@pytest.fixture()
def client():
    return TestClient(app_module.app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOMORROW = (date.today() + timedelta(days=1)).isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
TODAY = date.today().isoformat()


def _log_tension(client, logged_by: str = "user-A", headers: dict | None = None):
    return client.post(
        "/tensions",
        json={"description": "Something feels off", "logged_by": logged_by},
        headers=headers or {},
    )


def _seed_decision() -> int:
    db = next(override_get_db())
    d = DecisionModel(
        loomio_poll_id=1,
        title="Test decision",
        status="passed",
        raw_payload=json.dumps({}),
        stance_counts=json.dumps({}),
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d.id


# ---------------------------------------------------------------------------
# Fix 1 — log_tension: X-Actor-User-Id must match logged_by
# ---------------------------------------------------------------------------

class TestLogTensionActorEnforcement:
    def test_no_header_accepted(self, client):
        r = _log_tension(client, logged_by="user-A")
        assert r.status_code == 201

    def test_matching_header_accepted(self, client):
        r = _log_tension(client, logged_by="user-A",
                         headers={"X-Actor-User-Id": "user-A"})
        assert r.status_code == 201

    def test_mismatched_header_rejected(self, client):
        r = _log_tension(client, logged_by="user-A",
                         headers={"X-Actor-User-Id": "user-B"})
        assert r.status_code == 403
        assert "logged_by" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Fix 2 — list_tensions: scoped to actor when header present
# ---------------------------------------------------------------------------

class TestListTensionsScoping:
    def _seed(self, client):
        _log_tension(client, logged_by="user-A")
        _log_tension(client, logged_by="user-A")
        _log_tension(client, logged_by="user-B")

    def test_no_header_returns_all(self, client):
        self._seed(client)
        r = client.get("/tensions")
        assert r.status_code == 200
        assert r.json()["total"] == 3

    def test_header_scopes_to_actor_a(self, client):
        self._seed(client)
        r = client.get("/tensions", headers={"X-Actor-User-Id": "user-A"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert all(t["logged_by"] == "user-A" for t in data["tensions"])

    def test_header_scopes_to_actor_b(self, client):
        self._seed(client)
        r = client.get("/tensions", headers={"X-Actor-User-Id": "user-B"})
        assert r.status_code == 200
        assert r.json()["total"] == 1


# ---------------------------------------------------------------------------
# Fix 3 — update_tension: X-Actor-User-Id must match updated_by
# ---------------------------------------------------------------------------

class TestUpdateTensionActorEnforcement:
    def _create_tension(self, client, user: str = "user-A") -> int:
        r = _log_tension(client, logged_by=user)
        assert r.status_code == 201
        return r.json()["id"]

    def test_owner_can_update_without_header(self, client):
        tid = self._create_tension(client)
        r = client.patch(f"/tensions/{tid}",
                         json={"updated_by": "user-A", "status": "in_progress"})
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

    def test_matching_header_accepted(self, client):
        tid = self._create_tension(client)
        r = client.patch(f"/tensions/{tid}",
                         json={"updated_by": "user-A", "status": "in_progress"},
                         headers={"X-Actor-User-Id": "user-A"})
        assert r.status_code == 200

    def test_mismatched_header_rejected(self, client):
        """Actor header says user-B but updated_by says user-A — identity mismatch."""
        tid = self._create_tension(client)
        r = client.patch(f"/tensions/{tid}",
                         json={"updated_by": "user-A", "status": "in_progress"},
                         headers={"X-Actor-User-Id": "user-B"})
        assert r.status_code == 403
        assert "updated_by" in r.json()["detail"]

    def test_non_owner_update_rejected(self, client):
        """Non-owner updated_by is rejected regardless of header."""
        tid = self._create_tension(client)
        r = client.patch(f"/tensions/{tid}",
                         json={"updated_by": "user-B", "status": "resolved"})
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Fix 4 — set_review_date: must be a future date
# ---------------------------------------------------------------------------

class TestSetReviewDateValidation:
    def test_future_date_accepted(self, client):
        did = _seed_decision()
        r = client.patch(f"/decisions/{did}/review",
                         json={"review_date": TOMORROW})
        assert r.status_code == 200
        assert r.json()["review_date"] == TOMORROW

    def test_past_date_rejected(self, client):
        did = _seed_decision()
        r = client.patch(f"/decisions/{did}/review",
                         json={"review_date": YESTERDAY})
        assert r.status_code == 422

    def test_today_rejected(self, client):
        """Today is not in the future."""
        did = _seed_decision()
        r = client.patch(f"/decisions/{did}/review",
                         json={"review_date": TODAY})
        assert r.status_code == 422
