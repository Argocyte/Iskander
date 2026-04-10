"""
Mattermost bot API client for the provisioner service.

Provides:
  - post_welcome             : post a welcome message to the member onboarding channel
  - search_and_redact_posts  : case-insensitive whole-word name replacement in message bodies
"""
from __future__ import annotations

import os
import re

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


def search_and_redact_posts(old_name: str, new_name: str) -> int:
    """
    Find all Mattermost posts containing old_name and replace with new_name.

    Uses whole-word, case-insensitive matching so partial substrings are not
    corrupted. Paginates until all matching posts are processed.

    Requires the bot account to have the ``edit_others_posts`` permission.
    Returns the count of posts updated.
    """
    headers = {
        "Authorization": f"Bearer {MATTERMOST_BOT_TOKEN}",
        "Content-Type": "application/json",
    }
    # Compile pattern once — whole-word, case-insensitive
    pattern = re.compile(r"\b" + re.escape(old_name) + r"\b", re.IGNORECASE)
    updated = 0
    page = 0
    per_page = 60

    with httpx.Client(timeout=max(_TIMEOUT, 60)) as client:
        while True:
            search_resp = client.post(
                f"{MATTERMOST_URL}/api/v4/posts/search",
                json={"terms": old_name, "is_or_search": False, "page": page, "per_page": per_page},
                headers=headers,
            )
            search_resp.raise_for_status()
            data = search_resp.json()
            posts = data.get("posts") or {}

            for post_id, post in posts.items():
                original = post.get("message", "")
                replaced = pattern.sub(new_name, original)
                if replaced == original:
                    continue  # no match after whole-word filter
                patch_resp = client.put(
                    f"{MATTERMOST_URL}/api/v4/posts/{post_id}/patch",
                    json={"message": replaced},
                    headers=headers,
                )
                patch_resp.raise_for_status()
                updated += 1

            if len(posts) < per_page:
                break
            page += 1

    return updated
