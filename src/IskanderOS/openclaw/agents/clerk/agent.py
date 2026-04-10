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
Before calling any write tool (`loomio_create_discussion`, `mattermost_post_message`,
`provision_member`, `dr_log_tension`, `dr_update_tension`, `dr_set_review_date`), you MUST:
1. Show the member what you are about to do and get their confirmation (in your text response)
2. In a SEPARATE tool-use round, call `glass_box_log` first — on its own, not combined with write tools
3. Only AFTER glass_box_log succeeds, call the write tool in the NEXT round

The system enforces this at the code level. If you combine glass_box_log and a write tool
in the same response, the write tool will be rejected. Always separate them into distinct rounds.

### S3 governance facilitation
- For tension logging: help the member articulate the situation, actor, need, and consequence.
  Use `draft_driver_statement` to show them the formatted version first. Only call `dr_log_tension`
  after they confirm the description is right.
- For review dates: confirm the date (YYYY-MM-DD) and the circle responsible before calling `dr_set_review_date`.
- `dr_list_due_reviews` and `dr_list_tensions` are read operations — no Glass Box required.
- `draft_driver_statement` is local formatting only — no Glass Box required.

### On votes
You can NEVER cast a vote or submit a stance on behalf of a member.
`loomio_create_proposal_draft` returns a formatted draft; tell the member to submit it.

### On individual vote data
MACI ensures individual vote data does not exist in any readable form. Do not attempt
to infer, reconstruct, or speculate about how any individual voted.
""".strip()


# ---------------------------------------------------------------------------
# Write-action guard — prior-round enforcement
# ---------------------------------------------------------------------------

_WRITE_TOOLS = {
    "loomio_create_discussion",
    "mattermost_post_message",
    "provision_member",
    "dr_log_tension",
    "dr_update_tension",
    "dr_set_review_date",
    "dr_update_accountability",
}


def _response_tool_names(content: list[Any]) -> list[str]:
    """Extract all tool names from a single LLM response."""
    return [b.name for b in content if getattr(b, "type", None) == "tool_use"]


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

    # Tracks whether glass_box_log completed successfully in a PRIOR tool-use round.
    # Write tools are blocked until this is True. Reset to False after each write
    # executes so every distinct write action requires its own preceding log entry.
    _glass_box_confirmed = False

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

        tool_names = _response_tool_names(response.content)
        write_tools_present = [n for n in tool_names if n in _WRITE_TOOLS]

        # Prior-round Glass Box enforcement:
        # Write tools are only allowed when glass_box_log has been confirmed in
        # a SEPARATE, PRIOR tool-use round. Combining them in the same response
        # still rejects the write tool — glass_box_log runs and sets the flag,
        # and the model retries the write in the next round.
        if write_tools_present and not _glass_box_confirmed:
            rejection = (
                f"Write tool(s) {write_tools_present} rejected: "
                "glass_box_log must complete in a separate round BEFORE any write tool. "
                "Call glass_box_log by itself, wait for it to succeed, then call the "
                "write tool in the following round."
            )
            logger.warning(
                "Glass Box prior-round violation | user=%s | write_tools=%s",
                user_id, write_tools_present,
            )
            tool_results = []
            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                if block.name in _WRITE_TOOLS:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"error": rejection}),
                        "is_error": True,
                    })
                else:
                    # Non-write tools (reads, glass_box_log) execute normally
                    result_dict = _execute_tool(block, user_id)
                    tool_results.append(result_dict)
                    # If glass_box_log succeeded here, arm the flag for the NEXT round
                    if block.name == "glass_box_log":
                        result_content = json.loads(result_dict.get("content", "{}"))
                        if "error" not in result_content:
                            _glass_box_confirmed = True
            messages.append({"role": "user", "content": tool_results})
            continue

        # Execute all tool calls, tracking Glass Box and write state
        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            logger.info("Clerk tool call: %s | user=%s", block.name, user_id)
            result_dict = _execute_tool(block, user_id)
            tool_results.append(result_dict)

            if block.name == "glass_box_log":
                # Arm the flag if glass_box_log succeeded (no write tools this round)
                result_content = json.loads(result_dict.get("content", "{}"))
                if "error" not in result_content:
                    _glass_box_confirmed = True

            if block.name in _WRITE_TOOLS:
                # Reset after each write — the next write needs its own log entry
                _glass_box_confirmed = False

        messages.append({"role": "user", "content": tool_results})

    logger.error("Clerk reached MAX_TOOL_ROUNDS without finishing | user=%s", user_id)
    return "I ran into a problem completing that request. Please try again or contact a fellow member."


def _execute_tool(block: Any, user_id: str) -> dict:
    """Execute a single tool call block and return its result dict."""
    tool_name = block.name
    tool_input = dict(block.input)

    # Inject actor_user_id for tools that need it.
    # dr_update_tension requires it to enforce ownership (#63).
    _ACTOR_TOOLS = {
        "glass_box_log",
        "loomio_create_discussion",
        "dr_log_tension",
        "dr_update_tension",
    }
    if tool_name in _ACTOR_TOOLS:
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
                target=tool_input.get("channel_id") or tool_input.get("group_key") or tool_input.get("username") or "unknown",
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
