"""
Loomio API client for the provisioner service.

Provides one operation:
  - add_member : add a member to a Loomio group by email and return the membership ID
"""
from __future__ import annotations

import os

import httpx

LOOMIO_URL: str = os.environ["LOOMIO_URL"].rstrip("/")
LOOMIO_API_KEY: str = os.environ["LOOMIO_API_KEY"]

_TIMEOUT = float(os.environ.get("PROVISIONER_HTTP_TIMEOUT", "30"))


def add_member(email: str, group_key: str) -> dict:
    """
    Add a member to a Loomio group.

    Calls POST /api/v1/memberships and returns
    ``{"loomio_membership_id": <int>}`` extracted from the first membership
    in the response.

    Raises ``httpx.HTTPStatusError`` if the API responds with a non-2xx status.
    """
    payload = {
        "membership": {
            "group_key": group_key,
            "email": email,
        }
    }
    headers = {
        "Authorization": f"Token {LOOMIO_API_KEY}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            f"{LOOMIO_URL}/api/v1/memberships",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    return {"loomio_membership_id": data["memberships"][0]["id"]}
