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

from .tools import TOOL_DEFINITIONS, TOOL_REGISTRY

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

### Critical tool ordering rule — strictly enforced
Before calling `loomio_create_discussion` or `mattermost_post_message`, you MUST:
1. Show the member what you are about to do and get their confirmation (in your text response)
2. In a SEPARATE tool-use round, call `glass_box_log` first — on its own, not combined with write tools
3. Only AFTER glass_box_log succeeds, call the write tool in the NEXT round

The system enforces this at the code level. If you combine glass_box_log and a write tool
in the same response, the write tool will be rejected. Always separate them into distinct rounds.

### On votes
You can NEVER cast a vote or submit a stance on behalf of a member.
`loomio_create_proposal_draft` returns a formatted draft; tell the member to submit it.

### On individual vote data
MACI ensures individual vote data does not exist in any readable form. Do not attempt
to infer, reconstruct, or speculate about how any individual voted.
""".strip()


# ---------------------------------------------------------------------------
# Write-action guard — round-level enforcement
# ---------------------------------------------------------------------------

_WRITE_TOOLS = {"loomio_create_discussion", "mattermost_post_message"}


def _response_tool_names(content: list[Any]) -> list[str]:
    """Extract all tool names from a single LLM response."""
    return [b.name for b in content if getattr(b, "type", None) == "tool_use"]


def _validate_response_ordering(content: list[Any]) -> str | None:
    """
    Validate tool ordering within a single response.

    Rules:
    - If a response contains a write tool, it must ALSO contain glass_box_log
      AND glass_box_log must appear before the write tool in the response.
    - If a response contains only glass_box_log (no write tools), that's fine —
      the write tool comes in the next round.

    Returns None if valid, or an error message string if invalid.
    """
    tool_blocks = [b for b in content if getattr(b, "type", None) == "tool_use"]
    names = [b.name for b in tool_blocks]

    write_tools_present = [n for n in names if n in _WRITE_TOOLS]
    if not write_tools_present:
        return None  # No write tools — nothing to enforce

    # Write tool present: glass_box_log must appear before it
    if "glass_box_log" not in names:
        return (
            f"Write tool(s) {write_tools_present} called without glass_box_log. "
            "Call glass_box_log first (in a separate round if needed)."
        )

    log_index = names.index("glass_box_log")
    for wt in write_tools_present:
        wt_index = names.index(wt)
        if log_index >= wt_index:
            return (
                f"glass_box_log must come BEFORE {wt} in the response. "
                "Reorder your tool calls: log first, then write."
            )

    return None  # Valid ordering


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
            "content": f"[Member: {username} | Channel: {channel_id}]\n\n{message}",
        }
    ]

    for _round in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            return _extract_text(response.content)

        if response.stop_reason != "tool_use":
            logger.warning("Unexpected stop_reason: %s", response.stop_reason)
            return _extract_text(response.content)

        # Validate tool ordering for this entire response before processing any tool
        ordering_error = _validate_response_ordering(response.content)
        if ordering_error:
            logger.warning("Tool ordering violation | user=%s | %s", user_id, ordering_error)
            # Reject all tool calls in this response and tell the model why
            tool_results = []
            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                if block.name in _WRITE_TOOLS:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"error": ordering_error}),
                        "is_error": True,
                    })
                else:
                    # glass_box_log and reads are fine even in a mixed response
                    tool_results.append(_execute_tool(block, user_id))
            messages.append({"role": "user", "content": tool_results})
            continue

        # Execute all tool calls in this response
        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            logger.info("Clerk tool call: %s | user=%s", block.name, user_id)
            tool_results.append(_execute_tool(block, user_id))

        messages.append({"role": "user", "content": tool_results})

    logger.error("Clerk reached MAX_TOOL_ROUNDS without finishing | user=%s", user_id)
    return "I ran into a problem completing that request. Please try again or contact a fellow member."


def _execute_tool(block: Any, user_id: str) -> dict:
    """Execute a single tool call block and return its result dict."""
    tool_name = block.name
    tool_input = dict(block.input)

    # Inject actor_user_id for tools that need it
    if tool_name in ("glass_box_log", "loomio_create_discussion"):
        tool_input["actor_user_id"] = user_id

    try:
        fn = TOOL_REGISTRY[tool_name]
        result = fn(**tool_input)
    except Exception:
        # Log full exception but return a generic error to prevent internal disclosure
        logger.exception("Tool %s failed | user=%s", tool_name, user_id)
        result = {"error": "Tool execution failed. The error has been logged."}

    # Log write action outcomes back to the Glass Box so the audit trail is complete.
    # glass_box_log itself is excluded to avoid infinite recursion.
    if tool_name in _WRITE_TOOLS and "error" not in result:
        try:
            from .tools import glass_box_log as _glass_box_log
            _glass_box_log(
                actor_user_id=user_id,
                action=f"outcome:{tool_name}",
                target=tool_input.get("channel_id") or tool_input.get("group_key") or "unknown",
                reasoning=json.dumps(result, default=str)[:500],
            )
        except Exception:
            # Outcome logging failure is non-fatal — the action already succeeded.
            logger.warning("Glass Box outcome log failed | tool=%s | user=%s", tool_name, user_id)

    return {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": json.dumps(result, default=str),
    }


def _extract_text(content: list[Any]) -> str:
    """Extract plain text from Anthropic response content blocks."""
    parts = [b.text for b in content if hasattr(b, "text")]
    return "\n".join(parts).strip() or "(no response)"
