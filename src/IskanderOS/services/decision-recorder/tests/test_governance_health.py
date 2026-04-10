"""
Tests for governance health report endpoints.

POST /governance/health-reports
GET  /governance/health-reports/latest
PATCH /governance/health-reports/{id}/suppress-nudge
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("LOOMIO_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "")

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db import Base, get_db
from main import app

# ---------------------------------------------------------------------------
# Test fixture — in-memory SQLite shared via StaticPool
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """TestClient backed by a fresh in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # drop_all before create_all because StaticPool reuses the same underlying
    # SQLite connection across test function calls — without this, the second
    # test sees indexes from the first test and raises OperationalError.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_report_payload(**overrides):
    base = {
        "lifecycle_stage": "growing",
        "signals": [
            {"id": "SIG-06", "name": "Governance debt", "severity": "advisory", "detected": True, "detail": "5 overdue"},
        ],
        "nudges": [
            {"id": "NUDGE-SIG-06", "signal_id": "SIG-06", "message": "You have overdue reviews.", "actions": []},
        ],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# POST /governance/health-reports
# ---------------------------------------------------------------------------

class TestStoreHealthReport:
    def test_store_returns_201_with_report(self, client):
        resp = client.post("/governance/health-reports", json=_valid_report_payload())
        assert resp.status_code == 201
        body = resp.json()
        assert body["lifecycle_stage"] == "growing"
        assert len(body["signals"]) == 1
        assert body["signals"][0]["id"] == "SIG-06"
        assert body["suppressed_nudges"] == []
        assert "id" in body
        assert "assessed_at" in body

    def test_store_no_lifecycle_stage(self, client):
        resp = client.post("/governance/health-reports", json=_valid_report_payload(lifecycle_stage=None))
        assert resp.status_code == 201
        assert resp.json()["lifecycle_stage"] is None

    def test_store_empty_signals_and_nudges(self, client):
        resp = client.post("/governance/health-reports", json={
            "lifecycle_stage": "founding",
            "signals": [],
            "nudges": [],
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["signals"] == []
        assert body["nudges"] == []

    def test_invalid_lifecycle_stage_rejected(self, client):
        resp = client.post("/governance/health-reports", json=_valid_report_payload(lifecycle_stage="galactic"))
        assert resp.status_code == 422

    def test_invalid_signal_severity_rejected(self, client):
        payload = _valid_report_payload(signals=[
            {"id": "SIG-99", "name": "Unknown", "severity": "catastrophic", "detected": True, "detail": "bad"},
        ])
        resp = client.post("/governance/health-reports", json=payload)
        assert resp.status_code == 422

    def test_signal_missing_severity_rejected(self, client):
        payload = _valid_report_payload(signals=[{"id": "SIG-99", "detected": True}])
        resp = client.post("/governance/health-reports", json=payload)
        assert resp.status_code == 422

    def test_all_valid_lifecycle_stages_accepted(self, client):
        for stage in ("founding", "growing", "maturing", "scaling", "federated"):
            resp = client.post("/governance/health-reports", json=_valid_report_payload(lifecycle_stage=stage))
            assert resp.status_code == 201, f"Stage '{stage}' was rejected"

    def test_all_valid_signal_severities_accepted(self, client):
        for severity in ("advisory", "warning", "urgent"):
            payload = _valid_report_payload(signals=[
                {"id": "SIG-01", "name": "Test", "severity": severity, "detected": False, "detail": "ok"},
            ])
            resp = client.post("/governance/health-reports", json=payload)
            assert resp.status_code == 201, f"Severity '{severity}' was rejected"

    def test_multiple_signals_stored(self, client):
        payload = {
            "lifecycle_stage": "maturing",
            "signals": [
                {"id": "SIG-05", "name": "Block rate spike", "severity": "warning", "detected": True, "detail": "3/10"},
                {"id": "SIG-06", "name": "Governance debt", "severity": "advisory", "detected": False, "detail": "0/5"},
                {"id": "SIG-07", "name": "Tension backlog", "severity": "advisory", "detected": True, "detail": "9 open"},
            ],
            "nudges": [],
        }
        resp = client.post("/governance/health-reports", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert len(body["signals"]) == 3
        ids = [s["id"] for s in body["signals"]]
        assert "SIG-05" in ids
        assert "SIG-07" in ids


# ---------------------------------------------------------------------------
# GET /governance/health-reports/latest
# ---------------------------------------------------------------------------

class TestGetLatestHealthReport:
    def test_404_when_no_reports(self, client):
        resp = client.get("/governance/health-reports/latest")
        assert resp.status_code == 404

    def test_returns_most_recent_report(self, client):
        client.post("/governance/health-reports", json=_valid_report_payload(lifecycle_stage="founding"))
        client.post("/governance/health-reports", json=_valid_report_payload(lifecycle_stage="growing"))

        resp = client.get("/governance/health-reports/latest")
        assert resp.status_code == 200
        # Should return the second (most recent) report
        assert resp.json()["lifecycle_stage"] == "growing"

    def test_report_contains_expected_fields(self, client):
        client.post("/governance/health-reports", json=_valid_report_payload())
        resp = client.get("/governance/health-reports/latest")
        assert resp.status_code == 200
        body = resp.json()
        for field in ("id", "assessed_at", "lifecycle_stage", "signals", "nudges", "suppressed_nudges"):
            assert field in body, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# PATCH /governance/health-reports/{id}/suppress-nudge
# ---------------------------------------------------------------------------

class TestSuppressNudge:
    def test_suppress_nudge_adds_to_suppressed(self, client):
        create_resp = client.post("/governance/health-reports", json=_valid_report_payload())
        report_id = create_resp.json()["id"]

        suppress_resp = client.patch(
            f"/governance/health-reports/{report_id}/suppress-nudge",
            json={"nudge_id": "NUDGE-SIG-06"},
        )
        assert suppress_resp.status_code == 200
        assert "NUDGE-SIG-06" in suppress_resp.json()["suppressed_nudges"]

    def test_suppress_idempotent(self, client):
        create_resp = client.post("/governance/health-reports", json=_valid_report_payload())
        report_id = create_resp.json()["id"]

        for _ in range(3):
            client.patch(
                f"/governance/health-reports/{report_id}/suppress-nudge",
                json={"nudge_id": "NUDGE-SIG-06"},
            )

        resp = client.get("/governance/health-reports/latest")
        assert resp.json()["suppressed_nudges"].count("NUDGE-SIG-06") == 1

    def test_suppress_nonexistent_report_returns_404(self, client):
        resp = client.patch(
            "/governance/health-reports/99999/suppress-nudge",
            json={"nudge_id": "NUDGE-SIG-06"},
        )
        assert resp.status_code == 404

    def test_suppress_empty_nudge_id_rejected(self, client):
        create_resp = client.post("/governance/health-reports", json=_valid_report_payload())
        report_id = create_resp.json()["id"]

        resp = client.patch(
            f"/governance/health-reports/{report_id}/suppress-nudge",
            json={"nudge_id": ""},
        )
        assert resp.status_code == 422

    def test_suppress_multiple_nudges(self, client):
        payload = _valid_report_payload(nudges=[
            {"id": "NUDGE-SIG-05", "signal_id": "SIG-05", "message": "test", "actions": []},
            {"id": "NUDGE-SIG-06", "signal_id": "SIG-06", "message": "test", "actions": []},
        ])
        create_resp = client.post("/governance/health-reports", json=payload)
        report_id = create_resp.json()["id"]

        client.patch(f"/governance/health-reports/{report_id}/suppress-nudge", json={"nudge_id": "NUDGE-SIG-05"})
        client.patch(f"/governance/health-reports/{report_id}/suppress-nudge", json={"nudge_id": "NUDGE-SIG-06"})

        resp = client.get("/governance/health-reports/latest")
        suppressed = resp.json()["suppressed_nudges"]
        assert "NUDGE-SIG-05" in suppressed
        assert "NUDGE-SIG-06" in suppressed
