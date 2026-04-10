"""
Wellbeing Agent tools.

Exposes:
  glass_box_log       — audit trail for all write actions (required before every write)
  update_member_name  — propagate name change across Authentik + Provisioner + redaction
  redact_old_name     — case-insensitive whole-word replacement in Mattermost + Loomio
  notify_name_change  — post an opt-in notification to the general channel
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

_DECISION_RECORDER_URL = os.environ.get("DECISION_RECORDER_URL", "http://decision-recorder:3000")
_PROVISIONER_URL = os.environ.get("PROVISIONER_URL", "http://provisioner:3001")
_MATTERMOST_URL = os.environ.get("MATTERMOST_URL", "").rstrip("/")
_MATTERMOST_BOT_TOKEN = os.environ.get("MATTERMOST_BOT_TOKEN", "")
_MATTERMOST_GENERAL_CHANNEL = os.environ.get("MATTERMOST_GENERAL_CHANNEL", "")
_INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")
_TIMEOUT = float(os.environ.get("WELLBEING_HTTP_TIMEOUT", "30"))


def _headers() -> dict:
    h: dict[str, str] = {"Content-Type": "application/json"}
    if _INTERNAL_SERVICE_TOKEN:
        h["Authorization"] = f"Bearer {_INTERNAL_SERVICE_TOKEN}"
    return h


def _mm_headers() -> dict:
    return {
        "Authorization": f"Bearer {_MATTERMOST_BOT_TOKEN}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Write-tool set — must be mirrored in agent.py
# ---------------------------------------------------------------------------

_WRITE_TOOLS = {"update_member_name", "redact_old_name", "notify_name_change"}


# ---------------------------------------------------------------------------
# Glass Box
# ---------------------------------------------------------------------------

def glass_box_log(
    *,
    actor_user_id: str,
    action: str,
    target: str,
    reasoning: str,
) -> dict:
    """
    Log an agent action to the Glass Box audit trail.

    Must be called before any write tool. The reasoning field must use
    [REDACTED] in place of any name being removed.
    """
    payload = {
        "actor": actor_user_id,
        "agent": "wellbeing",
        "action": action,
        "target": target,
        "reasoning": reasoning,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(
                f"{_DECISION_RECORDER_URL}/glass-box",
                json=payload,
                headers=_headers(),
            )
            resp.raise_for_status()
            return {"logged": True, "id": resp.json().get("id")}
    except Exception as exc:
        logger.error("Glass Box log failed: %s", exc)
        return {"logged": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# update_member_name
# ---------------------------------------------------------------------------

def update_member_name(*, username: str, new_display_name: str) -> dict:
    """
    Propagate a name change across Authentik + Provisioner.

    Flow:
    1. GET /members/{username} from Provisioner — get authentik_id and current display_name
    2. PUT /api/v3/core/users/{pk}/ in Authentik with new name
    3. PATCH /members/{username} in Provisioner with new display_name
    4. Invoke redact_old_name for free-text message redaction
    """
    with httpx.Client(timeout=_TIMEOUT) as client:
        # Step 1 — get current record
        get_resp = client.get(
            f"{_PROVISIONER_URL}/members/{username}",
            headers=_headers(),
        )
        get_resp.raise_for_status()
        member = get_resp.json()

    authentik_id = member.get("authentik_id")
    old_display_name = member.get("display_name", "")

    if not authentik_id:
        return {"error": f"No Authentik ID found for member {username}"}

    # Step 2 — update Authentik (critical: must succeed before anything else)
    authentik_url = os.environ.get("AUTHENTIK_URL", "").rstrip("/")
    authentik_token = os.environ.get("AUTHENTIK_API_TOKEN", "")
    if not authentik_url or not authentik_token:
        return {"error": "Authentik is not configured — cannot update name"}

    with httpx.Client(timeout=_TIMEOUT) as client:
        auth_resp = client.put(
            f"{authentik_url}/api/v3/core/users/{authentik_id}/",
            json={"name": new_display_name},
            headers={
                "Authorization": f"Bearer {authentik_token}",
                "Content-Type": "application/json",
            },
        )
        auth_resp.raise_for_status()

    # Step 3 — update Provisioner record
    with httpx.Client(timeout=_TIMEOUT) as client:
        patch_resp = client.patch(
            f"{_PROVISIONER_URL}/members/{username}",
            json={"display_name": new_display_name},
            headers=_headers(),
        )
        patch_resp.raise_for_status()

    # Step 4 — redact old name from message bodies (best-effort)
    redaction_result: dict[str, Any] = {}
    if old_display_name and old_display_name != new_display_name:
        try:
            redaction_result = redact_old_name(
                old_name=old_display_name,
                new_name=new_display_name,
                member_username=username,
            )
        except Exception as exc:
            logger.warning("Name redaction partial failure: %s", exc)
            redaction_result = {"error": str(exc)}

    return {
        "updated": True,
        "new_display_name": new_display_name,
        "redaction": redaction_result,
    }


# ---------------------------------------------------------------------------
# redact_old_name
# ---------------------------------------------------------------------------

def redact_old_name(*, old_name: str, new_name: str, member_username: str) -> dict:
    """
    Case-insensitive whole-word replacement of old_name with new_name
    across Mattermost message bodies and Loomio discussions/comments.

    Delegates to Provisioner's redaction endpoint to keep all external API
    calls within the provisioner service boundary.
    """
    with httpx.Client(timeout=max(_TIMEOUT, 120)) as client:
        resp = client.post(
            f"{_PROVISIONER_URL}/members/{member_username}/redact",
            json={"old_name": old_name, "new_name": new_name},
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# notify_name_change
# ---------------------------------------------------------------------------

def notify_name_change(*, new_display_name: str) -> dict:
    """
    Post an opt-in notification to the cooperative's general channel.
    Never mentions the old name.
    """
    if not _MATTERMOST_GENERAL_CHANNEL:
        return {"error": "MATTERMOST_GENERAL_CHANNEL not configured"}
    if not _MATTERMOST_URL or not _MATTERMOST_BOT_TOKEN:
        return {"error": "Mattermost not configured"}

    message = (
        f"{new_display_name} has updated their display name. "
        "Please use their current name going forward."
    )
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            f"{_MATTERMOST_URL}/api/v4/posts",
            json={"channel_id": _MATTERMOST_GENERAL_CHANNEL, "message": message},
            headers=_mm_headers(),
        )
        resp.raise_for_status()
        return {"notified": True, "post_id": resp.json().get("id")}


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic tool-use schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "glass_box_log",
        "description": (
            "Log a planned action to the cooperative's Glass Box audit trail. "
            "MUST be called before any write tool. Use [REDACTED] for any old "
            "name being removed — never log the old name in plaintext."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Short action name, e.g. 'update_member_name'",
                },
                "target": {
                    "type": "string",
                    "description": "The resource being acted on, e.g. the username",
                },
                "reasoning": {
                    "type": "string",
                    "description": (
                        "Why this action is being taken. Use [REDACTED] "
                        "in place of any name being removed."
                    ),
                },
            },
            "required": ["action", "target", "reasoning"],
        },
    },
    {
        "name": "update_member_name",
        "description": (
            "Update a member's display name across the entire platform: "
            "Authentik (SSO), Provisioner record, and free-text redaction "
            "in Mattermost and Loomio. Authentik is updated first; if that "
            "fails the operation is aborted with no change. "
            "WRITE TOOL — requires glass_box_log in the previous round."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "The member's current username (login handle)",
                },
                "new_display_name": {
                    "type": "string",
                    "description": "The new display name the member has chosen",
                },
            },
            "required": ["username", "new_display_name"],
        },
    },
    {
        "name": "redact_old_name",
        "description": (
            "Case-insensitive, whole-word replacement of old_name with new_name "
            "in Mattermost message bodies and Loomio discussions/comments. "
            "Called automatically by update_member_name, but can be called "
            "independently to retry a partial redaction. "
            "WRITE TOOL — requires glass_box_log in the previous round."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "old_name": {
                    "type": "string",
                    "description": "The name to find and replace",
                },
                "new_name": {
                    "type": "string",
                    "description": "The replacement name",
                },
                "member_username": {
                    "type": "string",
                    "description": "The member's username (for scoping the search)",
                },
            },
            "required": ["old_name", "new_name", "member_username"],
        },
    },
    {
        "name": "notify_name_change",
        "description": (
            "Post an opt-in announcement to the cooperative's general channel. "
            "Only call this after the member explicitly consents. "
            "Never mentions the old name. "
            "WRITE TOOL — requires glass_box_log in the previous round."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "new_display_name": {
                    "type": "string",
                    "description": "The member's new display name",
                },
            },
            "required": ["new_display_name"],
        },
    },
]

TOOL_REGISTRY: dict[str, Any] = {
    "glass_box_log": glass_box_log,
    "update_member_name": update_member_name,
    "redact_old_name": redact_old_name,
    "notify_name_change": notify_name_change,
}
