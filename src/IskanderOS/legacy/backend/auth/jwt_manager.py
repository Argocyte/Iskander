"""
jwt_manager.py — Phase 19: JWT Token Issuance and Verification.

Issues access tokens (short-lived, 24h) and refresh tokens (long-lived, 7d)
after successful SIWE authentication. Tokens carry the member's Ethereum
address, DID, cooperative role, and on-chain member token ID.

Dependencies: python-jose[cryptography]
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from backend.config import settings

logger = logging.getLogger(__name__)

# Token type identifiers embedded in the JWT payload.
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


@dataclass
class TokenPayload:
    """Decoded JWT payload."""

    sub: str                     # Checksummed Ethereum address
    did: str | None              # W3C DID from CoopIdentity (None for guests)
    role: str                    # "steward", "worker-owner", "associate", "guest"
    member_token_id: int | None  # CoopIdentity SBT token ID (None for guests)
    chain_id: int                # EVM chain ID
    token_type: str              # "access" or "refresh"
    iat: datetime                # Issued at
    exp: datetime                # Expires at
    jti: str                     # Unique token ID


def create_access_token(
    address: str,
    did: str | None = None,
    role: str = "guest",
    member_token_id: int | None = None,
) -> str:
    """Issue a short-lived JWT access token.

    Parameters
    ----------
    address:
        Checksummed Ethereum address (the subject).
    did:
        W3C DID from CoopIdentity SBT, if the address holds one.
    role:
        Cooperative role from the on-chain MemberRecord.
    member_token_id:
        On-chain SBT token ID from CoopIdentity.

    Returns
    -------
    Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_expiry_minutes)

    payload: dict[str, Any] = {
        "sub": address,
        "did": did,
        "role": role,
        "member_token_id": member_token_id,
        "chain_id": settings.evm_chain_id,
        "token_type": TOKEN_TYPE_ACCESS,
        "iat": now,
        "exp": expire,
        "iss": settings.activitypub_domain,
        "jti": secrets.token_urlsafe(16),
    }

    return jwt.encode(payload, _get_secret(), algorithm=settings.jwt_algorithm)


def create_refresh_token(address: str) -> str:
    """Issue a long-lived JWT refresh token.

    Refresh tokens carry only the address and are used to obtain new
    access tokens without re-authenticating via SIWE.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_expiry_days)

    payload: dict[str, Any] = {
        "sub": address,
        "token_type": TOKEN_TYPE_REFRESH,
        "iat": now,
        "exp": expire,
        "iss": settings.activitypub_domain,
        "jti": secrets.token_urlsafe(16),
    }

    return jwt.encode(payload, _get_secret(), algorithm=settings.jwt_algorithm)


def verify_token(token: str, expected_type: str = TOKEN_TYPE_ACCESS) -> TokenPayload:
    """Decode and validate a JWT token.

    Parameters
    ----------
    token:
        The encoded JWT string.
    expected_type:
        Expected token type ("access" or "refresh").

    Returns
    -------
    TokenPayload with decoded claims.

    Raises
    ------
    ValueError:
        If the token is invalid, expired, or has the wrong type.
    """
    try:
        payload = jwt.decode(
            token,
            _get_secret(),
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": True},
        )
    except JWTError as exc:
        raise ValueError(f"Invalid JWT: {exc}") from exc

    token_type = payload.get("token_type", "")
    if token_type != expected_type:
        raise ValueError(f"Expected {expected_type} token, got {token_type}")

    return TokenPayload(
        sub=payload["sub"],
        did=payload.get("did"),
        role=payload.get("role", "guest"),
        member_token_id=payload.get("member_token_id"),
        chain_id=payload.get("chain_id", settings.evm_chain_id),
        token_type=token_type,
        iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
        exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        jti=payload.get("jti", ""),
    )


def _get_secret() -> str:
    """Return the JWT signing secret, raising clearly if not configured."""
    secret = settings.jwt_secret
    if not secret:
        raise RuntimeError(
            "JWT_SECRET is not configured. Set it in .env or environment variables. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
    return secret
