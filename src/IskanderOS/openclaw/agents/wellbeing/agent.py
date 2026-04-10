"""
Wellbeing Agent — main loop.

Receives a message from a cooperative member (via Mattermost bot event,
trigger word: @wellbeing), runs the Claude tool-use loop, and returns
a response. Every write action is enforced to go through glass_box_log first.

Handles dignity-critical operations: name changes, identity updates.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import anthropic

from .tools import TOOL_DEFINITIONS, TOOL_REGISTRY, _WRITE_TOOLS

logger = logging.getLogger(__name__)

MODEL = os.environ.get("WELLBEING_MODEL", os.environ.get("CLERK_MODEL", "claude-haiku-4-5-20251001"))
MAX_TOKENS = int(os.environ.get("WELLBEING_MAX_TOKENS", "4096"))
MAX_TOOL_ROUNDS = 10

_SOUL = (Path(__file__).parent / "SOUL.md").read_text()

SYSTEM_PROMPT = f"""
{_SOUL}

---

## Technical context

You are running as a bot in Mattermost. The member's message has been routed to you
because they used @wellbeing. You are separate from the Clerk — your domain is
member welfare, not governance administration.

### Critical tool ordering rule — strictly enforced
Before calling any write tool (`update_member_name`, `redact_old_name`, `notify_name_change`):
1. In a SEPARATE tool-use round, call `glass_box_log` first — on its own
2. In the reasoning field of glass_box_log, use [REDACTED] for any old name being removed
3. Only AFTER glass_box_log succeeds, call the write tool in the NEXT round

The system enforces this at the code level.

### Name change protocol
When a member asks to change their name:
1. Confirm the new name with them in a text response first
2. Log intent via glass_box_log (use [REDACTED] for the old name)
3. Call update_member_name — this handles Authentik, Provisioner, and redaction
4. Ask (in text, not a tool call): "Would you like me to let the group know you've updated your name?"
5. If they say yes, log via glass_box_log then call notify_name_change

Never volunteer or repeat the old name. Never ask why they want the change.
""".strip()


def _response_tool_names(content: list[Any]) -> list[str]:
    return [b.name for b in content if getattr(b, "type", None) == "tool_use"]


def _validate_response_ordering(content: list[Any]) -> str | None:
    tool_blocks = [b for b in content if getattr(b, "type", None) == "tool_use"]
    names = [b.name for b in tool_blocks]

    write_tools_present = [n for n in names if n in _WRITE_TOOLS]
    if not write_tools_present:
        return None

    if "glass_box_log" not in names:
        return (
            f"Write tool(s) {write_tools_present} called without glass_box_log. "
            "Call glass_box_log first."
        )

    log_index = names.index("glass_box_log")
    for wt in write_tools_present:
        wt_index = names.index(wt)
        if log_index >= wt_index:
            return (
                f"glass_box_log must come BEFORE {wt}. "
                "Reorder: log first, then write."
            )

    return None


def run(*, user_id: str, username: str, message: str, channel_id: str) -> str:
    """Process a member's message and return the Wellbeing Agent's response."""
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

        ordering_error = _validate_response_ordering(response.content)
        if ordering_error:
            logger.warning("Tool ordering violation | user=%s | %s", user_id, ordering_error)
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
                    tool_results.append(_execute_tool(block, user_id))
            messages.append({"role": "user", "content": tool_results})
            continue

        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            logger.info("Wellbeing tool call: %s | user=%s", block.name, user_id)
            tool_results.append(_execute_tool(block, user_id))

        messages.append({"role": "user", "content": tool_results})

    logger.error("Wellbeing agent reached MAX_TOOL_ROUNDS | user=%s", user_id)
    return "I ran into a problem. Please try again or contact a fellow member."


def _execute_tool(block: Any, user_id: str) -> dict:
    tool_name = block.name
    tool_input = dict(block.input)

    if tool_name == "glass_box_log":
        tool_input["actor_user_id"] = user_id

    try:
        fn = TOOL_REGISTRY[tool_name]
        result = fn(**tool_input)
    except Exception:
        logger.exception("Wellbeing tool %s failed | user=%s", tool_name, user_id)
        result = {"error": "Tool execution failed. The error has been logged."}

    # Log write action outcomes to the Glass Box (outcome record)
    if tool_name in _WRITE_TOOLS and "error" not in result:
        try:
            from .tools import glass_box_log as _glass_box_log
            _glass_box_log(
                actor_user_id=user_id,
                action=f"outcome:{tool_name}",
                target=tool_input.get("username") or tool_input.get("member_username") or "unknown",
                reasoning=json.dumps(result, default=str)[:500],
            )
        except Exception:
            logger.warning("Glass Box outcome log failed | tool=%s | user=%s", tool_name, user_id)

    return {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": json.dumps(result, default=str),
    }


def _extract_text(content: list[Any]) -> str:
    parts = [b.text for b in content if hasattr(b, "text")]
    return "\n".join(parts).strip() or "(no response)"
