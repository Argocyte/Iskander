"""
Steward agent — main loop.

Receives a message from a cooperative member (via Mattermost bot event),
runs the Claude tool-use loop against the permitted tool set, and returns
a response. The only write action is steward_post_financial_digest, which
must be preceded by glass_box_log in a separate tool-use round.

The Steward never moves money, never accesses individual member financial
data, and never touches Loomio or governance records.

<!-- contributor: 7b3f9e2a-14c8-4d6a-8f05-c2e1a3d90b47 | feature/steward-agent -->
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

MODEL = os.environ.get("STEWARD_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.environ.get("STEWARD_MAX_TOKENS", "4096"))
MAX_TOOL_ROUNDS = 10

_SOUL = (Path(__file__).parent / "SOUL.md").read_text()

SYSTEM_PROMPT = f"""
{_SOUL}

---

## Technical context

You are running as a bot in Mattermost. The member's message has been routed to you.
You have access to the cooperative's financial ledger and Mattermost via tools.

### Critical tool ordering rule — strictly enforced
Before calling `steward_post_financial_digest`, you MUST:
1. Call `steward_format_digest` and show the member the formatted digest
2. Receive explicit confirmation from the member that they want to post it
3. In a SEPARATE tool-use round, call `glass_box_log` on its own
4. Only AFTER glass_box_log succeeds, call `steward_post_financial_digest`

The system enforces this at the code level. If you call `steward_post_financial_digest`
in the same response as `glass_box_log`, the write will be rejected. Always separate
them into distinct rounds.

### On individual financial data
You must never report individual member financial figures. If asked:
"I only report cooperative-level aggregate figures. Individual financial data is private."

### On financial advice
You describe what the data shows. You never recommend what the cooperative should
do with its money. Surplus allocation and budget decisions go through Loomio.

### On transactions
You have no ability to move money or authorise transactions. If asked to do so,
say clearly: "I can't move money. Financial transactions require the treasurer and,
where above the threshold in your constitution, a Loomio consent decision."
""".strip()

# ---------------------------------------------------------------------------
# Write-action guard
# ---------------------------------------------------------------------------

_WRITE_TOOLS = {"steward_post_financial_digest"}


def _response_tool_names(content: list[Any]) -> list[str]:
    return [b.name for b in content if getattr(b, "type", None) == "tool_use"]




# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def run(*, user_id: str, username: str, message: str, channel_id: str) -> str:
    """
    Process a member's financial query and return the Steward's response.

    Args:
        user_id:    Mattermost user ID of the member
        username:   Display name for logging
        message:    The member's message text
        channel_id: Channel where the message was sent

    Returns:
        The Steward's response as a markdown string.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages: list[dict] = [
        {
            "role": "user",
            "content": f"[Member: {username} | Channel: {channel_id}]\n\n{message}",
        }
    ]

    # Tracks whether glass_box_log completed successfully in a PRIOR tool-use round.
    # Write tools are blocked until this is True. Reset to False after each write.
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

        # Prior-round Glass Box enforcement — same pattern as the Clerk agent.
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
                    result_dict = _execute_tool(block, user_id)
                    tool_results.append(result_dict)
                    if block.name == "glass_box_log":
                        result_content = json.loads(result_dict.get("content", "{}"))
                        if "error" not in result_content:
                            _glass_box_confirmed = True
            messages.append({"role": "user", "content": tool_results})
            continue

        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            logger.info("Steward tool call: %s | user=%s", block.name, user_id)
            result_dict = _execute_tool(block, user_id)
            tool_results.append(result_dict)

            if block.name == "glass_box_log":
                result_content = json.loads(result_dict.get("content", "{}"))
                if "error" not in result_content:
                    _glass_box_confirmed = True

            if block.name in _WRITE_TOOLS:
                _glass_box_confirmed = False

        messages.append({"role": "user", "content": tool_results})

    logger.error(
        "Steward reached MAX_TOOL_ROUNDS without finishing | user=%s", user_id
    )
    return (
        "I ran into a problem completing that request. "
        "Please try again or speak with the treasurer directly."
    )


def _execute_tool(block: Any, user_id: str) -> dict:
    """Execute a single tool call and return its result dict."""
    tool_name = block.name
    tool_input = dict(block.input)

    # Inject actor_user_id for tools that require it
    _ACTOR_TOOLS = {"glass_box_log", "steward_post_financial_digest"}
    if tool_name in _ACTOR_TOOLS:
        tool_input["actor_user_id"] = user_id

    try:
        fn = TOOL_REGISTRY[tool_name]
        result = fn(**tool_input)
    except Exception:
        logger.exception("Tool %s failed | user=%s", tool_name, user_id)
        result = {"error": "Tool execution failed. The error has been logged."}
        # Log write failures so the audit trail records what was attempted.
        if tool_name in _WRITE_TOOLS:
            try:
                from .tools import glass_box_log as _glass_box_log, GOVERNANCE_CHANNEL_ID
                _glass_box_log(
                    actor_user_id=user_id,
                    action=f"failure:{tool_name}",
                    target=GOVERNANCE_CHANNEL_ID,
                    reasoning="Tool raised an exception — see server logs for details.",
                )
            except Exception:
                logger.warning(
                    "Glass Box failure log also failed | tool=%s | user=%s", tool_name, user_id
                )

    # Log write outcomes to Glass Box so the audit trail is complete.
    if tool_name in _WRITE_TOOLS and "error" not in result:
        try:
            from .tools import glass_box_log as _glass_box_log, GOVERNANCE_CHANNEL_ID
            _glass_box_log(
                actor_user_id=user_id,
                action=f"outcome:{tool_name}",
                target=GOVERNANCE_CHANNEL_ID,  # resolved channel ID, not a literal string
                reasoning=json.dumps(result, default=str)[:500],
            )
        except Exception:
            logger.warning(
                "Glass Box outcome log failed | tool=%s | user=%s", tool_name, user_id
            )

    return {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": json.dumps(result, default=str),
    }


def _extract_text(content: list[Any]) -> str:
    parts = [b.text for b in content if hasattr(b, "text")]
    return "\n".join(parts).strip() or "(no response)"
