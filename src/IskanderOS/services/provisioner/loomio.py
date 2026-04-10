"""
Loomio API client for the provisioner service.

Provides:
  - add_member                : add a member to a Loomio group
  - search_and_redact_content : case-insensitive whole-word name replacement
                                in discussion titles/descriptions and comment bodies
"""
from __future__ import annotations

import os
import re

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


def search_and_redact_content(old_name: str, new_name: str) -> int:
    """
    Replace old_name with new_name in all Loomio discussion titles, descriptions,
    and comment bodies. Uses whole-word, case-insensitive matching.

    Paginates through all discussions in the configured group, then all comments
    within each discussion. Returns total count of items updated.
    """
    group_key = os.environ.get("LOOMIO_GROUP_KEY", "")
    headers = {
        "Authorization": f"Token {LOOMIO_API_KEY}",
        "Content-Type": "application/json",
    }
    pattern = re.compile(r"\b" + re.escape(old_name) + r"\b", re.IGNORECASE)
    updated = 0

    with httpx.Client(timeout=max(_TIMEOUT, 120)) as client:
        # Paginate discussions
        from_seq = 0
        while True:
            params: dict = {"per": 50}
            if group_key:
                params["group_key"] = group_key
            if from_seq:
                params["from"] = from_seq

            disc_resp = client.get(
                f"{LOOMIO_URL}/api/v1/discussions",
                params=params,
                headers=headers,
            )
            disc_resp.raise_for_status()
            disc_data = disc_resp.json()
            discussions = disc_data.get("discussions", [])

            for disc in discussions:
                disc_id = disc["id"]
                changes: dict = {}

                new_title = pattern.sub(new_name, disc.get("title", ""))
                if new_title != disc.get("title", ""):
                    changes["title"] = new_title

                new_desc = pattern.sub(new_name, disc.get("description", "") or "")
                if new_desc != (disc.get("description") or ""):
                    changes["description"] = new_desc

                if changes:
                    patch_resp = client.patch(
                        f"{LOOMIO_URL}/api/v1/discussions/{disc_id}",
                        json=changes,
                        headers=headers,
                    )
                    patch_resp.raise_for_status()
                    updated += 1

                # Paginate comments for this discussion
                comment_from = 0
                while True:
                    c_params: dict = {"discussion_id": disc_id, "per": 50}
                    if comment_from:
                        c_params["from"] = comment_from

                    c_resp = client.get(
                        f"{LOOMIO_URL}/api/v1/comments",
                        params=c_params,
                        headers=headers,
                    )
                    c_resp.raise_for_status()
                    c_data = c_resp.json()
                    comments = c_data.get("comments", [])

                    for comment in comments:
                        original_body = comment.get("body", "") or ""
                        new_body = pattern.sub(new_name, original_body)
                        if new_body != original_body:
                            cp_resp = client.patch(
                                f"{LOOMIO_URL}/api/v1/comments/{comment['id']}",
                                json={"body": new_body},
                                headers=headers,
                            )
                            cp_resp.raise_for_status()
                            updated += 1

                    if len(comments) < 50:
                        break
                    comment_from = comments[-1].get("id", 0)

            if len(discussions) < 50:
                break
            from_seq = discussions[-1].get("id", 0)

    return updated
