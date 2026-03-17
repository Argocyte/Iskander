"""
dependencies.py — Phase 19: FastAPI Auth Dependency Injection.

Provides reusable FastAPI dependencies for extracting and validating
JWT tokens from incoming requests. Enforces role-based access control
consistent with ICA cooperative principles (democratic member control).

Usage in routers:
    from backend.auth.dependencies import get_current_user, require_steward

    @router.post("/propose")
    async def submit_proposal(user: AuthenticatedUser = Depends(get_current_user)):
        ...

    @router.post("/execute", dependencies=[Depends(require_steward())])
    async def execute_proposal(...):
        ...
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, Header, HTTPException, Query, status

from backend.auth.jwt_manager import TokenPayload, verify_token

logger = logging.getLogger(__name__)


@dataclass
class AuthenticatedUser:
    """Authenticated user extracted from a valid JWT."""

    address: str                 # Checksummed Ethereum address
    did: str | None              # W3C DID from CoopIdentity (None for guests)
    role: str                    # "steward", "worker-owner", "associate", "guest"
    member_token_id: int | None  # CoopIdentity SBT token ID
    chain_id: int                # EVM chain ID


def _extract_bearer_token(authorization: str = Header(alias="Authorization")) -> str:
    """Extract the Bearer token from the Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must start with 'Bearer '",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization[7:]  # Strip "Bearer " prefix


async def get_current_user(
    token: str = Depends(_extract_bearer_token),
) -> AuthenticatedUser:
    """FastAPI dependency: extract and verify JWT, return authenticated user.

    Raises HTTP 401 if the token is missing, invalid, or expired.
    """
    try:
        payload: TokenPayload = verify_token(token, expected_type="access")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return AuthenticatedUser(
        address=payload.sub,
        did=payload.did,
        role=payload.role,
        member_token_id=payload.member_token_id,
        chain_id=payload.chain_id,
    )


def require_role(*allowed_roles: str) -> Callable:
    """FastAPI dependency factory: require the user to have one of the given roles.

    Usage:
        @router.post("/action", dependencies=[Depends(require_role("steward", "worker-owner"))])
        async def some_action(...):
            ...
    """

    async def _check_role(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"This action requires one of the following roles: "
                    f"{', '.join(allowed_roles)}. Your role: {user.role}"
                ),
            )
        return user

    return _check_role


def require_steward() -> Callable:
    """Shorthand: require the 'steward' role (Safe multi-sig operator)."""
    return require_role("steward")


async def optional_auth(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthenticatedUser | None:
    """FastAPI dependency: optionally authenticate if a Bearer token is present.

    Returns None if no Authorization header is provided.
    Returns AuthenticatedUser if a valid token is present.
    Raises HTTP 401 if a token is present but invalid.
    """
    if authorization is None or not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]
    try:
        payload: TokenPayload = verify_token(token, expected_type="access")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return AuthenticatedUser(
        address=payload.sub,
        did=payload.did,
        role=payload.role,
        member_token_id=payload.member_token_id,
        chain_id=payload.chain_id,
    )


async def optional_ws_auth(
    token: str | None = Query(default=None, alias="token"),
) -> AuthenticatedUser | None:
    """WebSocket auth dependency: extract token from query parameter.

    WebSocket connections cannot use Authorization headers, so the token
    is passed as a query parameter: /ws/events?token=<jwt>

    Returns None if no token is provided (unauthenticated in dev mode).
    """
    if token is None:
        return None

    try:
        payload: TokenPayload = verify_token(token, expected_type="access")
    except ValueError:
        return None  # Silently fail for WebSocket (no HTTP response to send)

    return AuthenticatedUser(
        address=payload.sub,
        did=payload.did,
        role=payload.role,
        member_token_id=payload.member_token_id,
        chain_id=payload.chain_id,
    )
