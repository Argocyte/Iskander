"""
Mattermost bot API client for the provisioner service.

Provides one operation:
  - post_welcome : post a welcome message to the member onboarding channel
"""
from __future__ import annotations

import os

import httpx

MATTERMOST_URL: str = os.environ["MATTERMOST_URL"].rstrip("/")
MATTERMOST_BOT_TOKEN: str = os.environ["MATTERMOST_BOT_TOKEN"]

_TIMEOUT = float(os.environ.get("PROVISIONER_HTTP_TIMEOUT", "30"))


def post_welcome(username: str, channel_id: str, display_name: str) -> dict:
    """
    Post a welcome message to the cooperative's onboarding channel.

    The message is directed at the new member by display name and username.
    ``channel_id`` should be a restricted onboarding channel, not #general.

    Calls POST /api/v4/posts and returns ``{"mattermost_post_id": "<id>"}``.
    Raises ``httpx.HTTPStatusError`` if the API responds with a non-2xx status.
    """
    message = (
        f":wave: Welcome to the cooperative, **{display_name}** (@{username})!\n\n"
        "Your account is ready. Please check your email for a setup link to complete your Mattermost login.\n"
        "Next steps: introduce yourself in this channel and read the member handbook."
    )
    payload = {
        "channel_id": channel_id,
        "message": message,
    }
    headers = {
        "Authorization": f"Bearer {MATTERMOST_BOT_TOKEN}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            f"{MATTERMOST_URL}/api/v4/posts",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    return {"mattermost_post_id": data["id"]}
