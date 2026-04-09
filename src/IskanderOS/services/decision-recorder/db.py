"""
SQLAlchemy models for the decision-recorder service.

Tables:
  decisions   — Loomio decision outcomes with IPFS CIDs
  glass_box   — Clerk agent action audit trail
  tensions    — Organisational tensions (S3: Navigate Via Tension pattern)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Index,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Base(DeclarativeBase):
    pass


class Decision(Base):
    """A recorded Loomio decision outcome."""
    __tablename__ = "decisions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    loomio_poll_id = Column(BigInteger, nullable=False, index=True)
    loomio_group_key = Column(String(64), nullable=True, index=True)
    title = Column(Text, nullable=False)
    outcome = Column(Text, nullable=True)          # outcome statement text
    status = Column(String(32), nullable=False)    # "passed", "blocked", "abstained"
    stance_counts = Column(Text, nullable=True)    # JSON: {"agree": 7, "disagree": 2}
    raw_payload = Column(Text, nullable=False)     # full Loomio webhook payload (JSON)
    ipfs_cid = Column(String(128), nullable=True)  # populated after IPFS pin
    loomio_url = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc))
    # S3: Evaluate and Evolve Agreements — review scheduling
    review_date = Column(Date, nullable=True, index=True)
    review_circle = Column(String(128), nullable=True)   # Loomio group key responsible
    review_status = Column(String(32), nullable=True,    # "pending" | "due" | "complete"
                           default="pending")

    __table_args__ = (
        Index("ix_decisions_recorded_at", "recorded_at"),
    )


class GlassBoxEntry(Base):
    """An audit trail entry for a Clerk agent action."""
    __tablename__ = "glass_box"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    actor = Column(String(128), nullable=False, index=True)   # Mattermost user ID
    agent = Column(String(64), nullable=False)                 # e.g. "clerk"
    action = Column(String(256), nullable=False)
    target = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))


class Tension(Base):
    """
    An organisational tension logged by a member via the Clerk.
    S3 pattern: Navigate Via Tension — gaps between current reality and what could be.
    Tensions are the raw material from which driver statements and proposals emerge.
    """
    __tablename__ = "tensions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    logged_by = Column(String(128), nullable=False, index=True)   # Mattermost user ID
    description = Column(Text, nullable=False)                     # What the member noticed
    domain = Column(String(128), nullable=True)                    # Circle/group this relates to
    driver_statement = Column(Text, nullable=True)                 # Formatted S3 driver (if drafted)
    status = Column(String(32), nullable=False, default="open")   # "open" | "in_progress" | "resolved"
    loomio_discussion_id = Column(BigInteger, nullable=True)       # Set when tension becomes discussion
    logged_at = Column(DateTime(timezone=True), nullable=False,
                       default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_tensions_logged_by", "logged_by"),
        Index("ix_tensions_status", "status"),
    )


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
