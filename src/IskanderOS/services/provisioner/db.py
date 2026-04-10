"""
SQLAlchemy models for the provisioner service.

ProvisioningRecord tracks the state of each member provisioning attempt
across all three systems: Authentik (SSO), Loomio (governance), Mattermost (chat).
The password_reset_url is a single-use, time-limited Authentik recovery link that
the Clerk surfaces to the requesting member — it is never stored permanently.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class ProvisioningRecord(Base):
    """
    Persists the result of each member provisioning run.

    Fields progress from False/None to True/set as each integration step
    succeeds. This allows safe idempotent re-runs: steps that already
    succeeded (authentik_exists=True, loomio_member=True, etc.) can be
    skipped on retry without duplicating accounts.
    """

    __tablename__ = "provisioning_records"

    # Integer (not BigInteger) so SQLite tests work; PostgreSQL maps this to INTEGER.
    # BigInteger is used for foreign-sourced IDs below (Loomio IDs can be large).
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(128), nullable=False, unique=True, index=True)
    email = Column(String(256), nullable=False)
    display_name = Column(String(256), nullable=True)

    # Authentik SSO
    authentik_id = Column(String(128), nullable=True)       # UUID assigned by Authentik
    authentik_exists = Column(Boolean, nullable=False, default=False)

    # Loomio governance
    loomio_membership_id = Column(BigInteger, nullable=True)
    loomio_member = Column(Boolean, nullable=False, default=False)

    # Mattermost chat
    mattermost_post_id = Column(String(128), nullable=True)  # welcome post ID
    mattermost_notified = Column(Boolean, nullable=False, default=False)

    # Single-use recovery link from Authentik /recovery/ endpoint.
    # Surfaced to the requesting member via Clerk response; not for long-term storage.
    password_reset_url = Column(Text, nullable=True)

    provisioned_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


def get_db():
    """FastAPI dependency: yield a database session, always close on exit."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables. Called at service startup."""
    Base.metadata.create_all(bind=engine)
