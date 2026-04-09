"""
Authentik admin API client for the provisioner service.

Provides two operations:
  - create_user  : create an SSO account and return its Authentik UUID
  - get_recovery_link : generate a single-use, time-limited password-set URL

The recovery link pattern is deliberately chosen over setting a password
directly — the provisioner never knows or controls the member's credentials.
"""
from __future__ import annotations

import os

import httpx

AUTHENTIK_URL: str = os.environ["AUTHENTIK_URL"]
AUTHENTIK_API_TOKEN: str = os.environ["AUTHENTIK_API_TOKEN"]

_TIMEOUT = float(os.environ.get("PROVISIONER_HTTP_TIMEOUT", "30"))


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {AUTHENTIK_API_TOKEN}",
        "Content-Type": "application/json",
    }


def create_user(username: str, email: str, display_name: str) -> dict:
    """
    Create a new internal Authentik user account.

    Calls POST /api/v3/core/users/ and returns ``{"authentik_id": "<UUID string>"}``.
    Raises ``httpx.HTTPStatusError`` if the API responds with a non-2xx status.

    Idempotency is the caller's responsibility — this function does not check
    whether the user already exists before attempting creation.
    """
    payload = {
        "username": username,
        "email": email,
        "name": display_name,
        "is_active": True,
        "type": "internal",
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            f"{AUTHENTIK_URL}/api/v3/core/users/",
            json=payload,
            headers=_auth_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    return {"authentik_id": data["pk"]}


def get_recovery_link(authentik_id: str) -> str:
    """
    Generate a single-use, time-limited password-set URL for an existing user.

    Calls POST /api/v3/core/users/{authentik_id}/recovery/ with an empty body
    and returns the ``link`` string from the JSON response.

    This URL is surfaced to the member via the Clerk — the provisioner never
    sets a password on behalf of the user.

    Raises ``httpx.HTTPStatusError`` if the API responds with a non-2xx status.
    """
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            f"{AUTHENTIK_URL}/api/v3/core/users/{authentik_id}/recovery/",
            json={},
            headers=_auth_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    return data["link"]
