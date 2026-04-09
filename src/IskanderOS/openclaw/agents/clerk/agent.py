"""
Clerk agent — main loop.

Receives a message from a cooperative member (via Mattermost bot event),
runs the Claude tool-use loop against the permitted tool set, and returns
a response. Every write action is enforced to go through glass_box_log first.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import anthropic

from .tools import TOOL_DEFINITIONS, TOOL_REGISTRY, glass_box_log

logger = logging.getLogger(__name__)

MODEL = os.environ.get("CLERK_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.environ.get("CLERK_MAX_TOKENS", "4096"))
MAX_TOOL_ROUNDS = 10   # prevent infinite loops

# Load the SOUL document once at startup
_SOUL = (Path(__file__).parent / "SOUL.md").read_text()

SYSTEM_PROMPT = f"""
{_SOUL}

---

## Technical context

You are running as a bot in Mattermost. The member's message has been routed to you.
You have access to the cooperative's Loomio and Mattermost APIs via tools.

### Critical tool ordering rule
Before calling `loomio_create_discussion` or `mattermost_post_message`, you MUST:
1. Show the member what you are about to do and get their confirmation (in your text response)
2. Call `glass_box_log` with what you are doing and why
3. Then — and only then — call the write tool

If you are not certain the member has confirmed, do not call the write tool.

### On votes
You can NEVER cast a vote or submit a stance on behalf of a member.
`loomio_create_proposal_draft` returns a formatted draft; tell the member to submit it.

### On individual vote data
MACI ensures individual vote data does not exist in any readable form. Do not attempt
to infer, reconstruct, or speculate about how any individual voted.
""".strip()


# ---------------------------------------------------------------------------
# Write-action guard
# ---------------------------------------------------------------------------

_WRITE_TOOLS = {"loomio_create_discussion", "mattermost_post_message"}
_GLASS_BOX_REQUIRED_BEFORE: set[str] = _WRITE_TOOLS


def _check_glass_box_precondition(
    tool_name: str,
    tool_calls_in_round: list[dict],
) -> bool:
    """
    Returns True if glass_box_log was called earlier in this round
    (or in a previous round in this session).
    Write tools must not proceed without a preceding glass_box_log call.
    """
    if tool_name not in _GLASS_BOX_REQUIRED_BEFORE:
        return True
    return any(tc["name"] == "glass_box_log" for tc in tool_calls_in_round)


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def run(*, user_id: str, username: str, message: str, channel_id: str) -> str:
    """
    Process a member's message and return the Clerk's response text.

    Args:
        user_id:    Mattermost user ID of the member
        username:   Display name for logging
        message:    The member's message text
        channel_id: Channel where the message was sent (for context)

    Returns:
        The Clerk's response as a markdown string.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                f"[Member: {username} | Channel: {channel_id}]\n\n{message}"
            ),
        }
    ]

    tool_calls_this_session: list[dict] = []

    for _round in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Accumulate the assistant message
        messages.append({"role": "assistant", "content": response.content})

        # If no tool calls, we have the final answer
        if response.stop_reason == "end_turn":
            return _extract_text(response.content)

        if response.stop_reason != "tool_use":
            logger.warning("Unexpected stop_reason: %s", response.stop_reason)
            return _extract_text(response.content)

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            tool_name = block.name
            tool_input = block.input
            tool_calls_this_session.append({"name": tool_name, "input": tool_input})

            logger.info("Clerk tool call: %s | user=%s", tool_name, user_id)

            # Enforce glass_box_log precondition for write tools
            if tool_name in _GLASS_BOX_REQUIRED_BEFORE:
                if not _check_glass_box_precondition(tool_name, tool_calls_this_session[:-1]):
                    result = {
                        "error": (
                            f"Glass Box must be called before {tool_name}. "
                            "This is a safety requirement — log the action first."
                        )
                    }
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })
                    continue

            # Inject actor_user_id into write tool calls
            if tool_name == "glass_box_log":
                tool_input = {**tool_input, "actor_user_id": user_id}
            elif tool_name == "loomio_create_discussion":
                tool_input = {**tool_input, "actor_user_id": user_id}

            # Execute the tool
            try:
                fn = TOOL_REGISTRY[tool_name]
                result = fn(**tool_input)
            except Exception as exc:
                logger.exception("Tool %s failed", tool_name)
                result = {"error": str(exc)}

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, default=str),
            })

        messages.append({"role": "user", "content": tool_results})

    logger.error("Clerk reached MAX_TOOL_ROUNDS without finishing")
    return "I ran into a problem completing that request. Please try again or contact a fellow member."


def _extract_text(content: list[Any]) -> str:
    """Extract plain text from Anthropic response content blocks."""
    parts = []
    for block in content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts).strip() or "(no response)"
