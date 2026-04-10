"""
Librarian Agent — main loop.

Receives a message from a cooperative member (trigger word: @librarian),
runs the Claude tool-use loop, and returns a response.

The Librarian is a pure read agent — no write tools, no Glass Box enforcement
needed. All tools are safe to call in any order.
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

MODEL = os.environ.get("LIBRARIAN_MODEL", os.environ.get("CLERK_MODEL", "claude-haiku-4-5-20251001"))
MAX_TOKENS = int(os.environ.get("LIBRARIAN_MAX_TOKENS", "4096"))
MAX_TOOL_ROUNDS = 6  # Lower than Clerk — searches are fast

_SOUL = (Path(__file__).parent / "SOUL.md").read_text()

SYSTEM_PROMPT = f"""
{_SOUL}

---

## Technical context

You are running as a bot in Mattermost, triggered by @librarian. The member is
looking for documents or governance knowledge. Your tools:

- `nextcloud_search(query)` — search Nextcloud by file name / content
- `nextcloud_get_document(path)` — read a document's text (up to 8,000 chars)
- `commons_search(query)` — search the S3 governance pattern library

All tools are read-only. Use them freely in any order.

When returning file paths, format them as Nextcloud web links if possible,
or as clear path references the member can copy into their browser.

If you cannot find what the member needs, say so plainly and suggest
alternative places to look (Loomio discussions, direct search in Nextcloud,
asking a fellow member).
""".strip()


def run(*, user_id: str, username: str, message: str, channel_id: str) -> str:
    """Process a member's message and return the Librarian's response."""
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

        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            logger.info("Librarian tool call: %s | user=%s", block.name, user_id)
            tool_results.append(_execute_tool(block))

        messages.append({"role": "user", "content": tool_results})

    logger.error("Librarian reached MAX_TOOL_ROUNDS | user=%s", user_id)
    return "I had trouble finding an answer. Please try a more specific search or look directly in Nextcloud."


def _execute_tool(block: Any) -> dict:
    tool_name = block.name
    tool_input = dict(block.input)

    try:
        fn = TOOL_REGISTRY[tool_name]
        result = fn(**tool_input)
    except Exception:
        logger.exception("Librarian tool %s failed", tool_name)
        result = {"error": "Tool execution failed. Please try again."}

    return {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": json.dumps(result, default=str),
    }


def _extract_text(content: list[Any]) -> str:
    parts = [b.text for b in content if hasattr(b, "text")]
    return "\n".join(parts).strip() or "(no response)"
