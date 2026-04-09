"""
Tests for the provisioner FastAPI main.py.

Environment variables are set before any provisioner module is imported so that
module-level os.environ[] calls (in db.py, authentik.py, etc.) succeed.
"""
from __future__ import annotations

import os

# --- env setup BEFORE any provisioner import ---
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("AUTHENTIK_URL", "https://auth.example.coop")
os.environ.setdefault("AUTHENTIK_API_TOKEN", "test-token")
os.environ.setdefault("LOOMIO_URL", "https://loomio.example.coop")
os.environ.setdefault("LOOMIO_API_KEY", "test-key")
os.environ.setdefault("LOOMIO_GROUP_KEY", "test-group")
os.environ.setdefault("MATTERMOST_URL", "https://mm.example.coop")
os.environ.setdefault("MATTERMOST_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("MATTERMOST_ONBOARDING_CHANNEL", "chan-onboard")

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from provisioner.db import Base, get_db
from provisioner.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite DB override
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Return a TestClient with a fresh in-memory DB per test.

    Uses StaticPool so the same in-memory connection is shared across threads
    (TestClient runs the ASGI app in a thread).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

MOCK_AUTHENTIK_ID = "auth-uuid-123"
MOCK_RECOVERY_URL = "https://auth.example.coop/recovery/abc123"
MOCK_LOOMIO_MEMBERSHIP_ID = 42
MOCK_MATTERMOST_POST_ID = "post-xyz"

VALID_PAYLOAD = {
    "username": "alice",
    "email": "alice@example.coop",
    "display_name": "Alice Example",
}


def _patch_all_steps():
    """Return a context manager stack that mocks all three integration steps."""
    return (
        patch(
            "provisioner.main.create_user",
            return_value={"authentik_id": MOCK_AUTHENTIK_ID},
        ),
        patch(
            "provisioner.main.get_recovery_link",
            return_value=MOCK_RECOVERY_URL,
        ),
        patch(
            "provisioner.main.add_member",
            return_value={"loomio_membership_id": MOCK_LOOMIO_MEMBERSHIP_ID},
        ),
        patch(
            "provisioner.main.post_welcome",
            return_value={"mattermost_post_id": MOCK_MATTERMOST_POST_ID},
        ),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_provision_member_success(client):
    with (
        patch("provisioner.main.create_user", return_value={"authentik_id": MOCK_AUTHENTIK_ID}),
        patch("provisioner.main.get_recovery_link", return_value=MOCK_RECOVERY_URL),
        patch("provisioner.main.add_member", return_value={"loomio_membership_id": MOCK_LOOMIO_MEMBERSHIP_ID}),
        patch("provisioner.main.post_welcome", return_value={"mattermost_post_id": MOCK_MATTERMOST_POST_ID}),
    ):
        resp = client.post("/members", json=VALID_PAYLOAD)

    assert resp.status_code == 201
    data = resp.json()
    assert data["provisioned"] is True
    assert data["password_reset_url"] == MOCK_RECOVERY_URL
    assert data["authentik_id"] == MOCK_AUTHENTIK_ID
    assert data["loomio_membership_id"] == MOCK_LOOMIO_MEMBERSHIP_ID
    assert data["mattermost_post_id"] == MOCK_MATTERMOST_POST_ID
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.coop"


def test_provision_member_idempotent(client):
    with (
        patch("provisioner.main.create_user", return_value={"authentik_id": MOCK_AUTHENTIK_ID}),
        patch("provisioner.main.get_recovery_link", return_value=MOCK_RECOVERY_URL),
        patch("provisioner.main.add_member", return_value={"loomio_membership_id": MOCK_LOOMIO_MEMBERSHIP_ID}),
        patch("provisioner.main.post_welcome", return_value={"mattermost_post_id": MOCK_MATTERMOST_POST_ID}),
    ):
        resp1 = client.post("/members", json=VALID_PAYLOAD)
        resp2 = client.post("/members", json=VALID_PAYLOAD)

    assert resp1.status_code == 201
    assert resp2.status_code == 200
    # Both responses should have the same data
    data = resp2.json()
    assert data["username"] == "alice"
    assert data["provisioned"] is True


def test_provision_member_missing_fields(client):
    resp = client.post("/members", json={"username": "bob"})
    assert resp.status_code == 422


def test_provision_member_invalid_username(client):
    resp = client.post(
        "/members",
        json={"username": "Alice!!", "email": "alice@example.coop"},
    )
    assert resp.status_code == 422


def test_get_member_not_found(client):
    resp = client.get("/members/nobody")
    assert resp.status_code == 404


def test_provision_step_failure_returns_502(client):
    with (
        patch("provisioner.main.create_user", side_effect=Exception("Authentik down")),
    ):
        resp = client.post("/members", json=VALID_PAYLOAD)

    assert resp.status_code == 502
    assert "Provisioning step failed" in resp.json()["detail"]
