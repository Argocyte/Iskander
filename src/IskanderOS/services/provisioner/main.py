"""
Provisioner — member onboarding orchestrator.

Endpoints:
  POST /members              Provision a new cooperative member (Authentik + Loomio + Mattermost)
  GET  /members/{username}   Get provisioning status for a username
  GET  /health               Service health check
"""
from __future__ import annotations

import hmac
import logging
import os
import time
from collections import defaultdict
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from provisioner.authentik import create_user, get_recovery_link
from provisioner.loomio import add_member
from provisioner.mattermost import post_welcome
from provisioner.db import ProvisioningRecord, SessionLocal, create_tables, get_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("provisioner")

app = FastAPI(
    title="Provisioner",
    description="Member onboarding orchestrator — Authentik SSO, Loomio governance, Mattermost chat",
    version="0.1.0",
)

LOOMIO_GROUP_KEY = os.environ["LOOMIO_GROUP_KEY"]
MATTERMOST_ONBOARDING_CHANNEL = os.environ["MATTERMOST_ONBOARDING_CHANNEL"]
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")

# ---------------------------------------------------------------------------
# Rate limiting — sliding window (same pattern as decision-recorder)
# ---------------------------------------------------------------------------

_RATE_WINDOW = 60  # seconds
_PROVISION_MAX = 30   # POST /members — member provisioning is rare
_QUERY_MAX = 60       # GET /members/{username}
_rate_counters: dict[str, list[float]] = defaultdict(list)


def _rate_check(key: str, max_requests: int) -> None:
    now = time.monotonic()
    window_start = now - _RATE_WINDOW
    _rate_counters[key] = [t for t in _rate_counters[key] if t > window_start]
    if len(_rate_counters[key]) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded.",
        )
    _rate_counters[key].append(now)


# ---------------------------------------------------------------------------
# Security — internal caller verification (same pattern as decision-recorder)
# ---------------------------------------------------------------------------

def _verify_internal_caller(request: Request) -> None:
    """
    Verify the caller is an internal service when INTERNAL_SERVICE_TOKEN is set.
    Without a token configured, NetworkPolicy provides isolation.
    With a token, both layers enforce access.
    """
    if not INTERNAL_SERVICE_TOKEN:
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Internal service token required")
    if not hmac.compare_digest(auth[7:], INTERNAL_SERVICE_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid service token")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup() -> None:
    create_tables()
    logger.info("Provisioner ready.")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ProvisionMemberRequest(BaseModel):
    username: str = Field(..., max_length=128)
    email: str = Field(..., max_length=256)
    display_name: Optional[str] = Field(None, max_length=256)

    @field_validator("username")
    @classmethod
    def username_safe(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-z0-9_-]+$", v):
            raise ValueError(
                "username must only contain lowercase letters, digits, hyphens, or underscores"
            )
        return v

    @field_validator("email")
    @classmethod
    def email_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("email must not be empty")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record_to_dict(record: ProvisioningRecord) -> dict:
    return {
        "username": record.username,
        "email": record.email,
        "display_name": record.display_name,
        "authentik_id": record.authentik_id,
        "loomio_membership_id": record.loomio_membership_id,
        "mattermost_post_id": record.mattermost_post_id,
        "password_reset_url": record.password_reset_url,
        "provisioned": (
            record.authentik_exists
            and record.loomio_member
            and record.mattermost_notified
        ),
        "authentik_exists": record.authentik_exists,
        "loomio_member": record.loomio_member,
        "mattermost_notified": record.mattermost_notified,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/members")
def provision_member(
    body: ProvisionMemberRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Provision a new cooperative member across Authentik, Loomio, and Mattermost.

    Idempotent: if a fully-provisioned record already exists for this username,
    returns 200. If partially provisioned, resumes from where it left off.
    """
    _verify_internal_caller(request)

    client_host = request.client.host if request.client else "unknown"
    _rate_check(f"provision:{client_host}", _PROVISION_MAX)

    display_name = body.display_name or body.username

    # --- Check for existing record ---
    record = (
        db.query(ProvisioningRecord)
        .filter(ProvisioningRecord.username == body.username)
        .first()
    )

    is_new = record is None

    if record is not None and (
        record.authentik_exists and record.loomio_member and record.mattermost_notified
    ):
        # Fully provisioned — idempotent 200
        return _record_to_dict(record)

    if record is None:
        record = ProvisioningRecord(
            username=body.username,
            email=body.email,
            display_name=display_name,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    # --- Step A: Authentik ---
    if not record.authentik_exists:
        try:
            auth_result = create_user(body.username, body.email, display_name)
            recovery_url = get_recovery_link(auth_result["authentik_id"])
            record.authentik_id = auth_result["authentik_id"]
            record.password_reset_url = recovery_url
            record.authentik_exists = True
            db.commit()
        except Exception as exc:
            logger.error("Authentik provisioning failed for %s: %s", body.username, exc)
            raise HTTPException(
                status_code=502,
                detail="Provisioning step failed: authentik. Partial state saved — retry is safe.",
            )

    # --- Step B: Loomio ---
    if not record.loomio_member:
        try:
            loomio_result = add_member(body.email, LOOMIO_GROUP_KEY)
            record.loomio_membership_id = loomio_result["loomio_membership_id"]
            record.loomio_member = True
            db.commit()
        except Exception as exc:
            logger.error("Loomio provisioning failed for %s: %s", body.username, exc)
            raise HTTPException(
                status_code=502,
                detail="Provisioning step failed: loomio. Partial state saved — retry is safe.",
            )

    # --- Step C: Mattermost ---
    if not record.mattermost_notified:
        try:
            mm_result = post_welcome(body.username, MATTERMOST_ONBOARDING_CHANNEL, display_name)
            record.mattermost_post_id = mm_result["mattermost_post_id"]
            record.mattermost_notified = True
            db.commit()
        except Exception as exc:
            logger.error("Mattermost provisioning failed for %s: %s", body.username, exc)
            raise HTTPException(
                status_code=502,
                detail="Provisioning step failed: mattermost. Partial state saved — retry is safe.",
            )

    response_data = _record_to_dict(record)

    if is_new:
        from fastapi.responses import JSONResponse
        return JSONResponse(content=response_data, status_code=201)

    return response_data


@app.get("/members/{username}")
def get_member(
    username: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Get provisioning status for a member username."""
    client_host = request.client.host if request.client else "unknown"
    _rate_check(f"member-query:{client_host}", _QUERY_MAX)

    record = (
        db.query(ProvisioningRecord)
        .filter(ProvisioningRecord.username == username)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Member not found")

    return _record_to_dict(record)
