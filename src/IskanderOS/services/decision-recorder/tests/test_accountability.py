"""
Tests for accountability tracking on decisions (issue #94).

Covers:
  - PATCH /decisions/{id}/accountability — update status, notes, review_date
  - GET  /decisions/accountability/overdue — list decisions needing follow-up
  - X-Actor-User-Id enforcement on accountability updates
  - Validation: invalid status, past review_date
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("LOOMIO_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "")

import ipfs as _ipfs  # noqa: E402  (conftest adds service dir to sys.path)
_ipfs.pin_json = MagicMock(return_value="QmTestCID")  # type: ignore[attr-defined]

import main as app_module  # noqa: E402
from db import Base, Decision as DecisionModel, get_db  # noqa: E402

# ---------------------------------------------------------------------------
# Shared test DB
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
# Helper
# ---------------------------------------------------------------------------

TOMORROW = (date.today() + timedelta(days=1)).isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
IN_3_DAYS = (date.today() + timedelta(days=3)).isoformat()
IN_10_DAYS = (date.today() + timedelta(days=10)).isoformat()


def _seed_decision(status: str = "passed", review_days: int | None = None) -> int:
    db = next(override_get_db())
    d = DecisionModel(
        loomio_poll_id=99,
        title="Test decision",
        status=status,
        raw_payload=json.dumps({}),
        stance_counts=json.dumps({}),
        recorded_at=datetime.now(timezone.utc),
    )
    if review_days is not None:
        d.accountability_review_date = date.today() + timedelta(days=review_days)
        d.accountability_status = "not_started"
    db.add(d)
    db.commit()
    db.refresh(d)
    return d.id


# ---------------------------------------------------------------------------
# Basic accountability update
# ---------------------------------------------------------------------------

class TestAccountabilityUpdate:
    def test_update_status(self, client):
        did = _seed_decision()
        r = client.patch(
            f"/decisions/{did}/accountability",
            json={"status": "in_progress", "updated_by": "user-A"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["accountability_status"] == "in_progress"
        assert data["accountability_updated_at"] is not None

    def test_update_with_notes(self, client):
        did = _seed_decision()
        r = client.patch(
            f"/decisions/{did}/accountability",
            json={
                "status": "in_progress",
                "notes": "Working group formed, meets Thursdays",
                "updated_by": "user-A",
            },
        )
        assert r.status_code == 200
        assert r.json()["accountability_status"] == "in_progress"

    def test_update_with_future_review_date(self, client):
        did = _seed_decision()
        r = client.patch(
            f"/decisions/{did}/accountability",
            json={"status": "in_progress", "review_date": TOMORROW, "updated_by": "user-A"},
        )
        assert r.status_code == 200
        assert r.json()["accountability_review_date"] == TOMORROW

    def test_mark_implemented(self, client):
        did = _seed_decision()
        r = client.patch(
            f"/decisions/{did}/accountability",
            json={"status": "implemented", "updated_by": "user-A"},
        )
        assert r.status_code == 200
        assert r.json()["accountability_status"] == "implemented"

    def test_mark_not_applicable(self, client):
        did = _seed_decision()
        r = client.patch(
            f"/decisions/{did}/accountability",
            json={"status": "not_applicable", "updated_by": "user-A"},
        )
        assert r.status_code == 200

    def test_decision_not_found(self, client):
        r = client.patch(
            "/decisions/9999/accountability",
            json={"status": "in_progress", "updated_by": "user-A"},
        )
        assert r.status_code == 404

    def test_invalid_status_rejected(self, client):
        did = _seed_decision()
        r = client.patch(
            f"/decisions/{did}/accountability",
            json={"status": "completed", "updated_by": "user-A"},
        )
        assert r.status_code == 422

    def test_past_review_date_rejected(self, client):
        did = _seed_decision()
        r = client.patch(
            f"/decisions/{did}/accountability",
            json={"status": "in_progress", "review_date": YESTERDAY, "updated_by": "user-A"},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# X-Actor-User-Id enforcement
# ---------------------------------------------------------------------------

class TestAccountabilityActorEnforcement:
    def test_matching_header_accepted(self, client):
        did = _seed_decision()
        r = client.patch(
            f"/decisions/{did}/accountability",
            json={"status": "in_progress", "updated_by": "user-A"},
            headers={"X-Actor-User-Id": "user-A"},
        )
        assert r.status_code == 200

    def test_mismatched_header_rejected(self, client):
        did = _seed_decision()
        r = client.patch(
            f"/decisions/{did}/accountability",
            json={"status": "in_progress", "updated_by": "user-A"},
            headers={"X-Actor-User-Id": "user-B"},
        )
        assert r.status_code == 403
        assert "updated_by" in r.json()["detail"]

    def test_no_header_accepted(self, client):
        did = _seed_decision()
        r = client.patch(
            f"/decisions/{did}/accountability",
            json={"status": "in_progress", "updated_by": "user-A"},
        )
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Overdue accountability list
# ---------------------------------------------------------------------------

class TestOverdueAccountability:
    def test_returns_due_decisions(self, client):
        _seed_decision(review_days=3)   # due within 7 days
        _seed_decision(review_days=5)   # due within 7 days
        _seed_decision(review_days=30)  # not due yet

        r = client.get("/decisions/accountability/overdue", params={"days_ahead": 7})
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2

    def test_excludes_implemented(self, client):
        did = _seed_decision(review_days=3)
        client.patch(
            f"/decisions/{did}/accountability",
            json={"status": "implemented", "updated_by": "user-A"},
        )
        r = client.get("/decisions/accountability/overdue", params={"days_ahead": 7})
        assert r.json()["count"] == 0

    def test_excludes_not_applicable(self, client):
        did = _seed_decision(review_days=3)
        client.patch(
            f"/decisions/{did}/accountability",
            json={"status": "not_applicable", "updated_by": "user-A"},
        )
        r = client.get("/decisions/accountability/overdue", params={"days_ahead": 7})
        assert r.json()["count"] == 0

    def test_no_review_date_excluded(self, client):
        """Decisions with no accountability_review_date are not returned."""
        _seed_decision()  # no review_days
        r = client.get("/decisions/accountability/overdue", params={"days_ahead": 7})
        assert r.json()["count"] == 0

    def test_decision_summary_includes_accountability(self, client):
        """Decision list endpoint exposes accountability_status for Clerk."""
        _seed_decision()
        r = client.get("/decisions")
        assert r.status_code == 200
        d = r.json()["decisions"][0]
        assert "accountability_status" in d
        assert d["accountability_status"] == "not_started"
