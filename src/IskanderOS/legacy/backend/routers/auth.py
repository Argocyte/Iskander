"""
auth.py — Phase 19: SIWE Authentication API Router.

Endpoints:
  POST /auth/nonce   — Generate a random nonce for SIWE message construction.
  POST /auth/login   — Verify SIWE message + signature, issue JWT tokens.
  POST /auth/refresh — Refresh an expired access token using a refresh token.
  POST /auth/logout  — Invalidate a refresh token (server-side blocklist).

The login flow:
  1. Client calls POST /auth/nonce → receives { nonce }.
  2. Client constructs a SIWE message with the nonce and signs it with their wallet.
  3. Client calls POST /auth/login with { message, signature } → receives JWT tokens.
  4. Client uses the access_token in Authorization: Bearer <token> for protected endpoints.

Anti-wealth-bias: Addresses without a CoopIdentity SBT are still allowed to login
with role="guest". Meatspace users who interact via the custodial credit system
can authenticate through a steward-assisted proxy flow (future phase).
"""
from __future__ import annotations

import logging
import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.auth.jwt_manager import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from backend.auth.siwe import verify_siwe_message
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ── In-memory nonce store (production: use Redis with TTL) ────────────────────
# Maps nonce → expiry timestamp. Cleaned on access.
_nonce_store: dict[str, float] = {}
_NONCE_TTL_SECONDS = 300  # 5 minutes

# ── In-memory refresh token blocklist (production: use Redis) ─────────────────
_revoked_jtis: set[str] = set()


def _clean_expired_nonces() -> None:
    """Remove expired nonces from the store."""
    now = time.time()
    expired = [n for n, exp in _nonce_store.items() if exp < now]
    for n in expired:
        del _nonce_store[n]


# ── Schemas ───────────────────────────────────────────────────────────────────


class NonceResponse(BaseModel):
    nonce: str = Field(..., description="Random nonce for SIWE message construction")


class LoginRequest(BaseModel):
    message: str = Field(..., description="The full SIWE message string")
    signature: str = Field(..., description="Hex-encoded signature (with or without 0x prefix)")


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(..., description="Access token expiry in seconds")
    user: dict[str, Any] = Field(..., description="Authenticated user profile")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="The refresh token from login response")


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


# ── POST /auth/nonce ──────────────────────────────────────────────────────────


@router.post("/nonce", response_model=NonceResponse)
async def generate_nonce() -> dict[str, str]:
    """Generate a random nonce for SIWE message construction.

    The nonce expires after 5 minutes. The client must include this nonce
    in the SIWE message they sign. The server validates it during login.
    """
    _clean_expired_nonces()

    nonce = secrets.token_urlsafe(16)
    _nonce_store[nonce] = time.time() + _NONCE_TTL_SECONDS

    return {"nonce": nonce}


# ── POST /auth/login ─────────────────────────────────────────────────────────


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> dict[str, Any]:
    """Verify SIWE message + signature and issue JWT tokens.

    After signature verification, queries the CoopIdentity contract to fetch
    the member's SBT data (DID, role, trust score). Addresses without an SBT
    receive role="guest" — preserving anti-wealth-bias for off-chain users.
    """
    _clean_expired_nonces()

    # 1. Verify SIWE signature.
    try:
        result = verify_siwe_message(
            message=req.message,
            signature=req.signature,
            expected_domain=None,  # Validate in production
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"SIWE verification failed: {exc}",
        ) from exc

    # 2. Validate and consume nonce.
    nonce_expiry = _nonce_store.pop(result.nonce, None)
    if nonce_expiry is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired nonce. Call POST /auth/nonce first.",
        )
    if time.time() > nonce_expiry:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nonce has expired. Call POST /auth/nonce for a fresh nonce.",
        )

    # 3. Query CoopIdentity for on-chain membership data.
    member_data = await _query_coop_identity(result.address)

    did = member_data.get("did")
    role = member_data.get("role", "guest")
    member_token_id = member_data.get("token_id")
    trust_score = member_data.get("trust_score", 0)
    is_member = member_data.get("is_member", False)

    # 4. Issue JWT tokens.
    access_token = create_access_token(
        address=result.address,
        did=did,
        role=role,
        member_token_id=member_token_id,
    )
    refresh_token = create_refresh_token(result.address)

    logger.info(
        "Login successful: address=%s, role=%s, is_member=%s, smart_contract=%s",
        result.address,
        role,
        is_member,
        result.is_smart_contract,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": settings.jwt_access_expiry_minutes * 60,
        "user": {
            "address": result.address,
            "did": did,
            "role": role,
            "member_token_id": member_token_id,
            "trust_score": trust_score,
            "is_member": is_member,
            "is_smart_contract": result.is_smart_contract,
            "chain_id": result.chain_id,
        },
    }


# ── POST /auth/refresh ───────────────────────────────────────────────────────


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(req: RefreshRequest) -> dict[str, Any]:
    """Issue a new access token from a valid refresh token.

    The refresh token itself is not rotated — it remains valid until its
    own expiry or explicit logout.
    """
    try:
        payload = verify_token(req.refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {exc}",
        ) from exc

    # Check blocklist.
    if payload.jti in _revoked_jtis:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked.",
        )

    # Re-query on-chain data to get fresh role/DID.
    member_data = await _query_coop_identity(payload.sub)

    access_token = create_access_token(
        address=payload.sub,
        did=member_data.get("did"),
        role=member_data.get("role", "guest"),
        member_token_id=member_data.get("token_id"),
    )

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": settings.jwt_access_expiry_minutes * 60,
    }


# ── POST /auth/logout ────────────────────────────────────────────────────────


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(req: LogoutRequest) -> None:
    """Invalidate a refresh token by adding its JTI to the blocklist.

    In production, use Redis with TTL matching the refresh token expiry
    so revoked tokens are automatically cleaned up.
    """
    try:
        payload = verify_token(req.refresh_token, expected_type=TOKEN_TYPE_REFRESH)
        _revoked_jtis.add(payload.jti)
        logger.info("Refresh token revoked for address=%s", payload.sub)
    except ValueError:
        pass  # Token already invalid — no-op.


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _query_coop_identity(address: str) -> dict[str, Any]:
    """Query the CoopIdentity contract for membership data.

    STUB: Returns guest defaults. Production implementation will use web3.py
    to call CoopIdentity.memberToken(address) and memberRecords[tokenId].
    """
    # TODO (Phase 19E Step 28): Replace with actual web3.py calls:
    #   w3 = get_web3()
    #   identity_contract = w3.eth.contract(address=..., abi=COOP_IDENTITY_ABI)
    #   token_id = identity_contract.functions.memberToken(address).call()
    #   if token_id > 0:
    #       record = identity_contract.functions.memberRecords(token_id).call()
    #       return {"did": record.did, "role": record.role, "trust_score": record.trustScore, ...}

    logger.info("STUB: CoopIdentity query for %s — returning guest defaults", address[:15])
    return {
        "did": None,
        "role": "guest",
        "token_id": None,
        "trust_score": 0,
        "is_member": False,
    }
