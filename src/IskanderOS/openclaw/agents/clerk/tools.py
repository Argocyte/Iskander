"""
Clerk agent tool implementations.

Each tool maps to a real API call. Before any tool that writes to external
systems, glass_box_log() MUST be called. This is enforced in agent.py.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

LOOMIO_BASE = os.environ["LOOMIO_URL"].rstrip("/")
LOOMIO_API_KEY = os.environ["LOOMIO_API_KEY"]
MATTERMOST_BASE = os.environ["MATTERMOST_URL"].rstrip("/")
MATTERMOST_BOT_TOKEN = os.environ["MATTERMOST_BOT_TOKEN"]
GLASS_BOX_BASE = os.environ.get("GLASS_BOX_URL", "http://decision-recorder:3000")

_http = httpx.Client(timeout=15)


# ---------------------------------------------------------------------------
# Glass Box — every write action is logged here first
# ---------------------------------------------------------------------------

def glass_box_log(
    *,
    actor_user_id: str,
    action: str,
    target: str,
    reasoning: str,
) -> dict[str, Any]:
    """
    Record a Clerk action in the Glass Box audit trail.
    Must be called BEFORE taking any action that affects cooperative systems.
    Returns the log entry with its ID.
    """
    payload = {
        "actor": actor_user_id,
        "agent": "clerk",
        "action": action,
        "target": target,
        "reasoning": reasoning,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    resp = _http.post(f"{GLASS_BOX_BASE}/log", json=payload)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Loomio — read operations (no Glass Box required)
# ---------------------------------------------------------------------------

def _loomio_get(path: str, params: dict | None = None) -> Any:
    resp = _http.get(
        f"{LOOMIO_BASE}/api/v1/{path}",
        params=params,
        headers={"Authorization": f"Token {LOOMIO_API_KEY}"},
    )
    resp.raise_for_status()
    return resp.json()


def loomio_list_proposals(group_key: str | None = None) -> list[dict]:
    """List open proposals. Optionally filter by group key."""
    params = {"status": "open"}
    if group_key:
        params["group_key"] = group_key
    data = _loomio_get("polls", params)
    return [
        {
            "id": p["id"],
            "title": p["title"],
            "closing_at": p["closing_at"],
            "votes_count": p["votes_count"],
            "stance_counts": p["stance_counts"],
            "description": p.get("description", "")[:200],
        }
        for p in data.get("polls", [])
    ]


def loomio_get_proposal(poll_id: int) -> dict:
    """Get a specific proposal with its current outcome."""
    data = _loomio_get(f"polls/{poll_id}")
    poll = data["polls"][0]
    return {
        "id": poll["id"],
        "title": poll["title"],
        "description": poll["description"],
        "closing_at": poll["closing_at"],
        "status": poll["status"],
        "outcome": poll.get("outcome"),
        "votes_count": poll["votes_count"],
        "stance_counts": poll["stance_counts"],
    }


def loomio_list_discussions(group_key: str | None = None, limit: int = 10) -> list[dict]:
    """List recent discussions."""
    params = {"order": "last_activity_at", "per": limit}
    if group_key:
        params["group_key"] = group_key
    data = _loomio_get("discussions", params)
    return [
        {
            "id": d["id"],
            "title": d["title"],
            "last_activity_at": d["last_activity_at"],
            "items_count": d["items_count"],
            "description": d.get("description", "")[:200],
        }
        for d in data.get("discussions", [])
    ]


def loomio_get_discussion(discussion_id: int) -> dict:
    """Get a specific discussion with recent activity."""
    data = _loomio_get(f"discussions/{discussion_id}")
    discussion = data["discussions"][0]
    return {
        "id": discussion["id"],
        "title": discussion["title"],
        "description": discussion["description"],
        "last_activity_at": discussion["last_activity_at"],
        "items_count": discussion["items_count"],
    }


def loomio_search(query: str) -> list[dict]:
    """Search discussions and proposals by keyword."""
    data = _loomio_get("search", {"q": query})
    results = []
    for item in data.get("discussions", [])[:5]:
        results.append({"type": "discussion", "id": item["id"], "title": item["title"]})
    for item in data.get("polls", [])[:5]:
        results.append({"type": "proposal", "id": item["id"], "title": item["title"]})
    return results


# ---------------------------------------------------------------------------
# Loomio — write operations (Glass Box required before calling)
# ---------------------------------------------------------------------------

def _loomio_post(path: str, payload: dict) -> Any:
    resp = _http.post(
        f"{LOOMIO_BASE}/api/v1/{path}",
        json=payload,
        headers={"Authorization": f"Token {LOOMIO_API_KEY}"},
    )
    resp.raise_for_status()
    return resp.json()


def loomio_create_discussion(
    *,
    group_key: str,
    title: str,
    description: str,
    actor_user_id: str,
) -> dict:
    """
    Create a new discussion thread in Loomio.
    Glass Box MUST be called before this function.
    """
    data = _loomio_post("discussions", {
        "discussion": {
            "group_key": group_key,
            "title": title,
            "description": description,
            "private": True,
        }
    })
    discussion = data["discussions"][0]
    return {
        "id": discussion["id"],
        "title": discussion["title"],
        "url": f"{LOOMIO_BASE}/d/{discussion['key']}",
    }


def loomio_create_proposal_draft(
    *,
    discussion_id: int,
    title: str,
    description: str,
    poll_type: str = "proposal",
    closing_in_days: int = 7,
) -> str:
    """
    Returns a formatted draft proposal that the member can review and submit
    themselves. The Clerk NEVER submits a vote — it only drafts.
    This function does NOT call the API; it returns a formatted text preview.
    """
    closing = "7 days from when you submit"
    return (
        f"**Draft proposal — please review before submitting in Loomio:**\n\n"
        f"**Title:** {title}\n\n"
        f"**Description:**\n{description}\n\n"
        f"**Type:** {poll_type}\n"
        f"**Closes:** {closing}\n\n"
        f"To submit: open the discussion in Loomio and click 'Start proposal'.\n"
        f"Discussion link: {LOOMIO_BASE}/d/{discussion_id}"
    )


# ---------------------------------------------------------------------------
# Mattermost — write operations (Glass Box required before calling)
# ---------------------------------------------------------------------------

def _mm_post(path: str, payload: dict) -> Any:
    resp = _http.post(
        f"{MATTERMOST_BASE}/api/v4/{path}",
        json=payload,
        headers={"Authorization": f"Bearer {MATTERMOST_BOT_TOKEN}"},
    )
    resp.raise_for_status()
    return resp.json()


def mattermost_post_message(*, channel_id: str, message: str) -> dict:
    """
    Post a message to a Mattermost channel.
    Glass Box MUST be called before this function.
    """
    data = _mm_post("posts", {"channel_id": channel_id, "message": message})
    return {"post_id": data["id"], "create_at": data["create_at"]}


# ---------------------------------------------------------------------------
# Tool definitions for the Anthropic API tool_use format
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "glass_box_log",
        "description": (
            "Log an action to the Glass Box audit trail. "
            "MUST be called before any write action (creating discussions, posting messages). "
            "Returns a log entry ID confirming the action was recorded."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Short description of what you are about to do"},
                "target": {"type": "string", "description": "The resource being acted on (e.g. 'Loomio discussion', 'Mattermost #governance')"},
                "reasoning": {"type": "string", "description": "Why you are taking this action"},
            },
            "required": ["action", "target", "reasoning"],
        },
    },
    {
        "name": "loomio_list_proposals",
        "description": "List open proposals in Loomio. Returns title, closing date, and vote counts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_key": {"type": "string", "description": "Optional: filter by cooperative group key"},
            },
        },
    },
    {
        "name": "loomio_get_proposal",
        "description": "Get details of a specific proposal including current outcome.",
        "input_schema": {
            "type": "object",
            "properties": {
                "poll_id": {"type": "integer", "description": "Loomio proposal/poll ID"},
            },
            "required": ["poll_id"],
        },
    },
    {
        "name": "loomio_list_discussions",
        "description": "List recent discussions in Loomio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_key": {"type": "string", "description": "Optional: filter by cooperative group key"},
                "limit": {"type": "integer", "description": "Max results to return (default 10)"},
            },
        },
    },
    {
        "name": "loomio_get_discussion",
        "description": "Get a specific discussion with its content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "discussion_id": {"type": "integer", "description": "Loomio discussion ID"},
            },
            "required": ["discussion_id"],
        },
    },
    {
        "name": "loomio_search",
        "description": "Search Loomio discussions and proposals by keyword.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "loomio_create_discussion",
        "description": (
            "Create a new discussion thread in Loomio. "
            "REQUIRES glass_box_log to be called first. "
            "REQUIRES explicit member confirmation before calling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "group_key": {"type": "string", "description": "Cooperative group key"},
                "title": {"type": "string", "description": "Discussion title"},
                "description": {"type": "string", "description": "Discussion description (markdown)"},
            },
            "required": ["group_key", "title", "description"],
        },
    },
    {
        "name": "loomio_create_proposal_draft",
        "description": (
            "Return a formatted draft proposal for the member to review. "
            "Does NOT submit to Loomio — the member must submit it themselves. "
            "Use this instead of directly creating proposals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "discussion_id": {"type": "integer", "description": "Discussion to attach the proposal to"},
                "title": {"type": "string"},
                "description": {"type": "string", "description": "Full proposal text (markdown)"},
                "poll_type": {"type": "string", "enum": ["proposal", "count", "score", "ranked_choice"], "description": "Type of vote"},
                "closing_in_days": {"type": "integer", "description": "Days until the vote closes (default 7)"},
            },
            "required": ["discussion_id", "title", "description"],
        },
    },
    {
        "name": "mattermost_post_message",
        "description": (
            "Post a message to a Mattermost channel. "
            "REQUIRES glass_box_log to be called first. "
            "Only use when explicitly asked to post to a specific channel."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "Mattermost channel ID"},
                "message": {"type": "string", "description": "Message content (markdown)"},
            },
            "required": ["channel_id", "message"],
        },
    },
]

# Map tool names to functions
TOOL_REGISTRY: dict[str, Any] = {
    "glass_box_log": glass_box_log,
    "loomio_list_proposals": loomio_list_proposals,
    "loomio_get_proposal": loomio_get_proposal,
    "loomio_list_discussions": loomio_list_discussions,
    "loomio_get_discussion": loomio_get_discussion,
    "loomio_search": loomio_search,
    "loomio_create_discussion": loomio_create_discussion,
    "loomio_create_proposal_draft": loomio_create_proposal_draft,
    "mattermost_post_message": mattermost_post_message,
}
