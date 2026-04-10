"""
Tests for provisioner db.py — ProvisioningRecord model.

Uses an in-memory SQLite database so no external dependencies are needed.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set DATABASE_URL before importing provisioner.db (it reads env at import time)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from provisioner.db import Base, ProvisioningRecord  # noqa: E402


@pytest.fixture()
def db_session():
    """Provide a fresh in-memory SQLite session per test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_provisioning_record_created(db_session):
    """A ProvisioningRecord can be persisted and retrieved."""
    record = ProvisioningRecord(
        username="alice",
        email="alice@example.coop",
        display_name="Alice Example",
    )
    db_session.add(record)
    db_session.commit()

    fetched = db_session.query(ProvisioningRecord).filter_by(username="alice").first()
    assert fetched is not None
    assert fetched.email == "alice@example.coop"
    assert fetched.display_name == "Alice Example"
    assert fetched.authentik_exists is False
    assert fetched.loomio_member is False
    assert fetched.mattermost_notified is False
    assert fetched.password_reset_url is None
    assert fetched.provisioned_at is not None


def test_provisioning_record_full_fields(db_session):
    """All optional fields can be set and persisted."""
    record = ProvisioningRecord(
        username="bob",
        email="bob@example.coop",
        authentik_id="auth-uuid-123",
        authentik_exists=True,
        loomio_membership_id=42,
        loomio_member=True,
        mattermost_post_id="post-abc",
        mattermost_notified=True,
        password_reset_url="https://auth.example.coop/recovery/token123",
    )
    db_session.add(record)
    db_session.commit()

    fetched = db_session.query(ProvisioningRecord).filter_by(username="bob").first()
    assert fetched.authentik_id == "auth-uuid-123"
    assert fetched.authentik_exists is True
    assert fetched.loomio_membership_id == 42
    assert fetched.loomio_member is True
    assert fetched.mattermost_post_id == "post-abc"
    assert fetched.mattermost_notified is True
    assert fetched.password_reset_url == "https://auth.example.coop/recovery/token123"
