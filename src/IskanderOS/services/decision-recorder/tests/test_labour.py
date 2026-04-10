"""
Tests for DisCO three-value-stream labour tracking (issue #91).

Covers:
  - POST /labour — log a record; validation (value_type, hours, timestamps)
  - GET  /labour — list with actor scoping and value_type filtering
  - GET  /labour/summary — totals by value type + care ratio
  - X-Actor-User-Id enforcement on log_labour
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("LOOMIO_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "")

import ipfs as _ipfs  # noqa: E402
_ipfs.pin_json = MagicMock(return_value="QmTestCID")  # type: ignore[attr-defined]

import main as app_module  # noqa: E402
from db import Base, get_db  # noqa: E402

# ---------------------------------------------------------------------------
# Test DB
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

NOW = datetime.now(timezone.utc).isoformat()
HOUR_AGO = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


def _log(client, member_id="user-A", value_type="care", hours="1.0",
         task_category="governance.facilitation", headers=None):
    return client.post(
        "/labour",
        json={
            "member_id": member_id,
            "value_type": value_type,
            "task_category": task_category,
            "hours": hours,
            "timestamp_start": HOUR_AGO,
        },
        headers=headers or {},
    )


# ---------------------------------------------------------------------------
# POST /labour — basic creation and validation
# ---------------------------------------------------------------------------

class TestLogLabour:
    def test_log_care_work(self, client):
        r = _log(client, value_type="care")
        assert r.status_code == 201
        data = r.json()
        assert data["value_type"] == "care"
        assert data["hours"] == "1.0"
        assert data["member_id"] == "user-A"

    def test_log_productive_work(self, client):
        r = _log(client, value_type="productive", task_category="code.review")
        assert r.status_code == 201

    def test_log_reproductive_work(self, client):
        r = _log(client, value_type="reproductive", task_category="docs.update")
        assert r.status_code == 201

    def test_log_commons_work(self, client):
        r = _log(client, value_type="commons", task_category="commons.writing")
        assert r.status_code == 201

    def test_invalid_value_type_rejected(self, client):
        r = _log(client, value_type="invisible")
        assert r.status_code == 422

    def test_hours_below_minimum_rejected(self, client):
        r = _log(client, hours="0.1")
        assert r.status_code == 422

    def test_hours_above_maximum_rejected(self, client):
        r = _log(client, hours="25.0")
        assert r.status_code == 422

    def test_invalid_hours_string_rejected(self, client):
        r = _log(client, hours="lots")
        assert r.status_code == 422

    def test_decimal_hours_accepted(self, client):
        r = _log(client, hours="0.25")
        assert r.status_code == 201
        assert r.json()["hours"] == "0.25"

    def test_with_optional_fields(self, client):
        r = client.post("/labour", json={
            "member_id": "user-A",
            "value_type": "care",
            "task_category": "onboarding.welcome",
            "task_description": "Welcomed three new members",
            "hours": "2.0",
            "timestamp_start": HOUR_AGO,
            "timestamp_end": NOW,
            "notes": "Covered coop values and governance workflow",
        })
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# X-Actor-User-Id enforcement
# ---------------------------------------------------------------------------

class TestLabourActorEnforcement:
    def test_no_header_accepted(self, client):
        r = _log(client, member_id="user-A")
        assert r.status_code == 201

    def test_matching_header_accepted(self, client):
        r = _log(client, member_id="user-A", headers={"X-Actor-User-Id": "user-A"})
        assert r.status_code == 201

    def test_mismatched_header_rejected(self, client):
        r = _log(client, member_id="user-A", headers={"X-Actor-User-Id": "user-B"})
        assert r.status_code == 403
        assert "member_id" in r.json()["detail"]


# ---------------------------------------------------------------------------
# GET /labour — listing and filtering
# ---------------------------------------------------------------------------

class TestListLabour:
    def _seed(self, client):
        _log(client, member_id="user-A", value_type="care")
        _log(client, member_id="user-A", value_type="productive")
        _log(client, member_id="user-B", value_type="reproductive")

    def test_no_header_returns_all(self, client):
        self._seed(client)
        r = client.get("/labour")
        assert r.status_code == 200
        assert r.json()["total"] == 3

    def test_actor_header_scopes_to_member(self, client):
        self._seed(client)
        r = client.get("/labour", headers={"X-Actor-User-Id": "user-A"})
        assert r.status_code == 200
        assert r.json()["total"] == 2

    def test_explicit_member_id_filter(self, client):
        self._seed(client)
        r = client.get("/labour", params={"member_id": "user-B"})
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_value_type_filter(self, client):
        self._seed(client)
        r = client.get("/labour", params={"value_type": "care"})
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_invalid_value_type_filter_rejected(self, client):
        r = client.get("/labour", params={"value_type": "invisible"})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /labour/summary — totals by value type
# ---------------------------------------------------------------------------

class TestLabourSummary:
    def _seed(self, client):
        _log(client, member_id="user-A", value_type="care", hours="2.0")
        _log(client, member_id="user-A", value_type="productive", hours="4.0")
        _log(client, member_id="user-A", value_type="reproductive", hours="1.0")
        _log(client, member_id="user-B", value_type="care", hours="3.0")

    def test_cooperative_summary(self, client):
        self._seed(client)
        r = client.get("/labour/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["scope"] == "cooperative"
        assert data["by_type"]["care"] == 5.0   # user-A 2h + user-B 3h
        assert data["by_type"]["productive"] == 4.0
        assert data["total_hours"] == 10.0

    def test_member_summary(self, client):
        self._seed(client)
        r = client.get("/labour/summary", params={"member_id": "user-A"})
        assert r.status_code == 200
        data = r.json()
        assert data["scope"] == "user-A"
        assert data["total_hours"] == 7.0

    def test_care_ratio_present(self, client):
        self._seed(client)
        r = client.get("/labour/summary")
        data = r.json()
        assert "care_ratio" in data
        # care 5.0 / total 10.0 = 0.5
        assert data["care_ratio"] == 0.5

    def test_empty_cooperative_returns_zeros(self, client):
        r = client.get("/labour/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["total_hours"] == 0.0
        assert data["care_ratio"] == 0.0
