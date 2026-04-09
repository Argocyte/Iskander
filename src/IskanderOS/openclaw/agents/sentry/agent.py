"""
Sentry agent — main loop and scheduled check entrypoint.

Two entry points:
  - run()                — responds to a member's on-demand infrastructure query
                           via Mattermost bot event (same pattern as Clerk/Steward)
  - run_scheduled_check() — called by a cron job; runs full health check and
                            posts alerts to #ops automatically if thresholds exceeded.
                            Uses actor_user_id='sentry-scheduler' in Glass Box entries.

The only write action is sentry_post_ops_alert. It must be preceded by
glass_box_log in a separate tool-use round.

<!-- contributor: 7b3f9e2a-14c8-4d6a-8f05-c2e1a3d90b47 | feature/sentry-agent -->
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

MODEL = os.environ.get("SENTRY_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.environ.get("SENTRY_MAX_TOKENS", "4096"))
MAX_TOOL_ROUNDS = 10

_SOUL = (Path(__file__).parent / "SOUL.md").read_text()

SYSTEM_PROMPT = f"""
{_SOUL}

---

## Technical context

You are running as an infrastructure monitor. You have access to the cooperative's
infrastructure health tools (Beszel, Backrest, IPFS, PostgreSQL) via tools.

### Critical tool ordering rule — strictly enforced
Before calling `sentry_post_ops_alert`, you MUST:
1. Gather the health data using read tools first
2. Determine that an alert threshold has been exceeded
3. In a SEPARATE tool-use round, call `glass_box_log` on its own
4. Only AFTER glass_box_log succeeds, call `sentry_post_ops_alert`

### On automated scheduled checks
When running as a scheduled check (message contains "[SCHEDULED CHECK]"),
you should:
1. Call `sentry_get_full_health_summary` to gather all metrics at once
2. If `healthy` is False, format a clear alert and post it to #ops
3. If `healthy` is True, do not post — log only if explicitly configured to do so
4. Use actor_user_id='sentry-scheduler' in glass_box_log and sentry_post_ops_alert

### Alert format
Alerts should follow this structure:
```
⚠️ Infrastructure Alert — [subsystem]

[Specific metric and value] exceeds threshold ([threshold value]).

Observed: [timestamp]
Action needed: [what a human should check or do]
```

### On remedial action
You never restart services, change config, or modify access controls.
If asked to do so, say clearly: "I can't do that — I observe and report.
For remedial action, [describe what the human should do or who to contact]."

### On Authentik
You can note unusual SSO patterns as observations to #ops. You cannot
modify user accounts, group memberships, or authentication policies.
Those changes require a Loomio consent decision.
""".strip()

# ---------------------------------------------------------------------------
# Write-action guard
# ---------------------------------------------------------------------------

_WRITE_TOOLS = {"sentry_post_ops_alert"}


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
        if log_index >= names.index(wt):
            return f"glass_box_log must appear BEFORE {wt}. Reorder: log first, then alert."

    return None


# ---------------------------------------------------------------------------
# Agent loops
# ---------------------------------------------------------------------------

def run(*, user_id: str, username: str, message: str, channel_id: str) -> str:
    """
    Respond to an on-demand infrastructure query from a cooperative member.

    The member triggers this by messaging the Sentry bot in Mattermost.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages: list[dict] = [
        {
            "role": "user",
            "content": f"[Member: {username} | Channel: {channel_id}]\n\n{message}",
        }
    ]

    return _run_loop(client, messages, user_id)


def run_scheduled_check() -> str | None:
    """
    Run an automated full health check and post alerts to #ops if needed.

    Called by a scheduler (e.g. Kubernetes CronJob, APScheduler).
    Returns the alert text posted, or None if all systems healthy.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                "[SCHEDULED CHECK] [Member: sentry-scheduler | Channel: ops]\n\n"
                "Run a full infrastructure health check. If any thresholds are exceeded "
                "and no alert has been posted for these conditions in the last hour, "
                "post an alert to #ops. If all systems are healthy, do not post."
            ),
        }
    ]

    result = _run_loop(client, messages, "sentry-scheduler")
    if result and result != "(no response)":
        return result
    return None


def _run_loop(
    client: anthropic.Anthropic,
    messages: list[dict],
    user_id: str,
) -> str:
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
            logger.info("Sentry tool call: %s | user=%s", block.name, user_id)
            tool_results.append(_execute_tool(block, user_id))

        messages.append({"role": "user", "content": tool_results})

    logger.error("Sentry reached MAX_TOOL_ROUNDS | user=%s", user_id)
    return "Health check incomplete after maximum rounds. Check logs."


def _execute_tool(block: Any, user_id: str) -> dict:
    tool_name = block.name
    tool_input = dict(block.input)

    _ACTOR_TOOLS = {"glass_box_log", "sentry_post_ops_alert"}
    if tool_name in _ACTOR_TOOLS:
        tool_input["actor_user_id"] = user_id

    try:
        fn = TOOL_REGISTRY[tool_name]
        result = fn(**tool_input)
    except Exception:
        logger.exception("Tool %s failed | user=%s", tool_name, user_id)
        result = {"error": "Tool execution failed. The error has been logged."}

    if tool_name in _WRITE_TOOLS and "error" not in result:
        try:
            from .tools import glass_box_log as _glass_box_log
            _glass_box_log(
                actor_user_id=user_id,
                action=f"outcome:{tool_name}",
                target=tool_input.get("channel_id", "ops-channel"),
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
