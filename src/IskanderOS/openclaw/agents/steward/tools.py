"""
Steward agent tool implementations.

The Steward reads from the cooperative's financial ledger and posts digests
to the governance channel. It never moves money or accesses individual
member financial data.

Tool categories:
  - glass_box_log     — audit trail (write actions only)
  - steward_get_*     — read operations against the steward-data service
  - steward_post_*    — write to Mattermost (Glass Box required first)

Thread safety: all HTTP calls use per-request httpx.Client instances.

<!-- contributor: 7b3f9e2a-14c8-4d6a-8f05-c2e1a3d90b47 | feature/steward-agent -->
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MATTERMOST_BASE = os.environ["MATTERMOST_URL"].rstrip("/")
MATTERMOST_BOT_TOKEN = os.environ["MATTERMOST_BOT_TOKEN"]
GOVERNANCE_CHANNEL_ID = os.environ["MATTERMOST_GOVERNANCE_CHANNEL_ID"]
GLASS_BOX_BASE = os.environ.get("GLASS_BOX_URL", "http://decision-recorder:3000")
# steward-data is a thin read-only service that wraps the cooperative's
# financial ledger tables in iskander_ledger. It exposes no write endpoints.
STEWARD_DATA_BASE = os.environ.get("STEWARD_DATA_URL", "http://steward-data:4000")

_TIMEOUT = float(os.environ.get("STEWARD_HTTP_TIMEOUT", "30"))

# Staleness threshold: flag data older than this many days
_STALENESS_DAYS = int(os.environ.get("STEWARD_STALENESS_DAYS", "30"))


def _http_client() -> httpx.Client:
    """Return a fresh per-request httpx.Client. Always use as a context manager."""
    return httpx.Client(timeout=_TIMEOUT)


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
    Record a Steward action in the Glass Box audit trail.
    Must be called BEFORE any write action (currently: steward_post_financial_digest).
    Returns the log entry with its ID.
    """
    payload = {
        "actor": actor_user_id,
        "agent": "steward",
        "action": action,
        "target": target,
        "reasoning": reasoning,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with _http_client() as client:
        resp = client.post(f"{GLASS_BOX_BASE}/log", json=payload)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Financial ledger — read operations (no Glass Box required)
# ---------------------------------------------------------------------------

def steward_get_treasury_summary() -> dict[str, Any]:
    """
    Return the cooperative's current treasury position.

    Aggregates across all registered accounts (operating, reserve, project).
    Returns the last-updated timestamp so staleness can be surfaced to members.
    Never returns individual member financial data.
    """
    with _http_client() as client:
        resp = client.get(f"{STEWARD_DATA_BASE}/treasury/summary")
        resp.raise_for_status()
        data = resp.json()

    last_updated = data.get("last_updated_at")
    stale = False
    if last_updated:
        age_days = (
            datetime.now(timezone.utc)
            - datetime.fromisoformat(last_updated)
        ).days
        stale = age_days > _STALENESS_DAYS

    return {
        "total_balance": data["total_balance"],
        "currency": data.get("currency", "GBP"),
        "accounts": data.get("accounts", []),   # [{"name": str, "balance": float}]
        "last_updated_at": last_updated,
        "stale": stale,
        "stale_days": age_days if stale else None,
    }


def steward_get_surplus_ytd() -> dict[str, Any]:
    """
    Return year-to-date income, expenditure, and surplus/deficit.

    Computed from financial_transactions for the current financial year.
    Budget figures included where set by the cooperative.
    """
    with _http_client() as client:
        resp = client.get(f"{STEWARD_DATA_BASE}/treasury/surplus-ytd")
        resp.raise_for_status()
        return resp.json()
    # Expected shape:
    # {
    #   "financial_year": "2025-2026",
    #   "income_ytd": float,
    #   "expenditure_ytd": float,
    #   "surplus_ytd": float,          # income - expenditure
    #   "budget_income": float | None,
    #   "budget_expenditure": float | None,
    #   "budget_surplus": float | None,
    #   "variance_income": float | None,
    #   "variance_expenditure": float | None,
    #   "as_of": str,                  # ISO timestamp
    # }


def steward_get_compliance_deadlines(days_ahead: int = 90) -> list[dict[str, Any]]:
    """
    Return compliance deadlines due within the next N days (default: 90).

    Includes regulatory filings, AGM requirements, annual return dates.
    Sorted by due_date ascending (soonest first).
    """
    with _http_client() as client:
        resp = client.get(
            f"{STEWARD_DATA_BASE}/compliance/deadlines",
            params={"days_ahead": days_ahead},
        )
        resp.raise_for_status()
        return resp.json().get("deadlines", [])
    # Each deadline:
    # {
    #   "id": int,
    #   "title": str,            e.g. "Annual return to FCA"
    #   "due_date": str,         ISO date
    #   "description": str,      what this filing requires
    #   "consequence": str,      what happens if missed
    #   "status": str,           "upcoming" | "overdue" | "completed"
    # }


def steward_get_recent_activity(limit: int = 10) -> list[dict[str, Any]]:
    """
    Return recent aggregate financial activity (last N transactions by category).

    Aggregate only — no individual attribution, no member names.
    """
    with _http_client() as client:
        resp = client.get(
            f"{STEWARD_DATA_BASE}/treasury/activity",
            params={"limit": limit},
        )
        resp.raise_for_status()
        return resp.json().get("transactions", [])
    # Each item:
    # {
    #   "date": str,
    #   "category": str,   e.g. "member_contribution", "rent", "operating_costs"
    #   "amount": float,
    #   "direction": "credit" | "debit",
    #   "description": str,
    # }


def steward_format_digest() -> str:
    """
    Build a plain-text financial digest combining treasury, surplus, and
    upcoming compliance deadlines.

    Returns the formatted text for member review — does NOT post it.
    Posting requires explicit member confirmation and glass_box_log first.
    """
    summary = steward_get_treasury_summary()
    surplus = steward_get_surplus_ytd()
    deadlines = steward_get_compliance_deadlines(days_ahead=60)

    currency = summary.get("currency", "GBP")
    balance = summary.get("total_balance", 0)
    stale = summary.get("stale", False)
    last_updated = summary.get("last_updated_at", "unknown")

    stale_warning = (
        f"\n⚠️ **Note:** Treasury data was last updated {summary.get('stale_days')} days ago "
        f"({last_updated[:10]}). Ask the treasurer to update the ledger.\n"
        if stale else ""
    )

    # Treasury section
    accounts_lines = "\n".join(
        f"  - {a['name']}: {currency} {a['balance']:,.2f}"
        for a in summary.get("accounts", [])
    ) or "  (no account breakdown available)"

    # Surplus section
    fy = surplus.get("financial_year", "current year")
    income = surplus.get("income_ytd", 0)
    expenditure = surplus.get("expenditure_ytd", 0)
    net = surplus.get("surplus_ytd", 0)
    net_label = "surplus" if net >= 0 else "deficit"

    budget_line = ""
    if surplus.get("budget_surplus") is not None:
        variance = net - surplus["budget_surplus"]
        direction = "ahead of" if variance >= 0 else "behind"
        budget_line = (
            f"\n  Budget surplus: {currency} {surplus['budget_surplus']:,.2f} "
            f"({currency} {abs(variance):,.2f} {direction} budget)"
        )

    # Compliance section
    if deadlines:
        deadline_lines = "\n".join(
            f"  - **{d['title']}** — due {d['due_date']}"
            + (" ⚠️ OVERDUE" if d["status"] == "overdue" else "")
            for d in deadlines[:5]
        )
    else:
        deadline_lines = "  No deadlines due in the next 60 days."

    digest = f"""## Monthly Financial Digest

{stale_warning}
### Treasury Position
**Total balance:** {currency} {balance:,.2f}
{accounts_lines}

### Year to Date ({fy})
- Income: {currency} {income:,.2f}
- Expenditure: {currency} {expenditure:,.2f}
- **Net {net_label}: {currency} {abs(net):,.2f}**{budget_line}

### Upcoming Compliance Deadlines
{deadline_lines}

---
*Prepared by the Steward agent. All figures are aggregate cooperative totals — no individual member data is included. To allocate surplus or respond to a compliance obligation, raise a proposal in Loomio.*"""

    return digest.strip()


# ---------------------------------------------------------------------------
# Mattermost — write operation (Glass Box required before calling)
# ---------------------------------------------------------------------------

def steward_post_financial_digest(
    *,
    actor_user_id: str,
    digest_text: str,
) -> dict[str, Any]:
    """
    Post a financial digest to the cooperative governance channel.
    Glass Box MUST be called before this function.
    """
    payload = {
        "channel_id": GOVERNANCE_CHANNEL_ID,
        "message": digest_text,
        "props": {
            "from_agent": "steward",
            "requested_by": actor_user_id,
        },
    }
    with _http_client() as client:
        resp = client.post(
            f"{MATTERMOST_BASE}/api/v4/posts",
            json=payload,
            headers={"Authorization": f"Bearer {MATTERMOST_BOT_TOKEN}"},
        )
        resp.raise_for_status()
        post = resp.json()
        return {
            "post_id": post["id"],
            "channel_id": post["channel_id"],
            "message_preview": digest_text[:120] + "...",
        }


# ---------------------------------------------------------------------------
# Tool registry — consumed by agent.py
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "glass_box_log",
        "description": (
            "Record a Steward action in the Glass Box audit trail. "
            "Call this BEFORE steward_post_financial_digest. "
            "Read operations do not require this call."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "actor_user_id": {
                    "type": "string",
                    "description": "Mattermost user ID of the member who requested this action.",
                },
                "action": {
                    "type": "string",
                    "description": "Short identifier for the action, e.g. 'post_financial_digest'.",
                },
                "target": {
                    "type": "string",
                    "description": "What is being acted on, e.g. '#governance channel'.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why you are taking this action.",
                },
            },
            "required": ["actor_user_id", "action", "target", "reasoning"],
        },
    },
    {
        "name": "steward_get_treasury_summary",
        "description": (
            "Return the cooperative's current treasury balance broken down by account. "
            "Includes a staleness flag if the data is more than 30 days old. "
            "Never returns individual member financial data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "steward_get_surplus_ytd",
        "description": (
            "Return year-to-date income, expenditure, and net surplus or deficit "
            "for the current financial year. Includes budget variance where set."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "steward_get_compliance_deadlines",
        "description": (
            "Return regulatory and governance compliance deadlines due within the "
            "next N days. Sorted soonest first. Includes what each deadline requires "
            "and the consequence of missing it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "How many days ahead to look. Default 90.",
                    "default": 90,
                },
            },
            "required": [],
        },
    },
    {
        "name": "steward_get_recent_activity",
        "description": (
            "Return the most recent aggregate financial transactions by category. "
            "No individual attribution — amounts and categories only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of recent transactions to return. Default 10.",
                    "default": 10,
                },
            },
            "required": [],
        },
    },
    {
        "name": "steward_format_digest",
        "description": (
            "Build a formatted financial digest combining treasury balance, YTD surplus, "
            "and upcoming compliance deadlines. Returns text for member review — "
            "does NOT post it. Use this to show the member the digest before they "
            "confirm posting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "steward_post_financial_digest",
        "description": (
            "Post a financial digest to the cooperative #governance channel. "
            "glass_box_log MUST be called before this. "
            "Show the member the digest first using steward_format_digest, "
            "get their confirmation, then log, then post."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "actor_user_id": {
                    "type": "string",
                    "description": "Mattermost user ID of the requesting member.",
                },
                "digest_text": {
                    "type": "string",
                    "description": "The digest content to post (from steward_format_digest).",
                },
            },
            "required": ["actor_user_id", "digest_text"],
        },
    },
]

TOOL_REGISTRY: dict[str, Any] = {
    "glass_box_log": glass_box_log,
    "steward_get_treasury_summary": steward_get_treasury_summary,
    "steward_get_surplus_ytd": steward_get_surplus_ytd,
    "steward_get_compliance_deadlines": steward_get_compliance_deadlines,
    "steward_get_recent_activity": steward_get_recent_activity,
    "steward_format_digest": steward_format_digest,
    "steward_post_financial_digest": steward_post_financial_digest,
}
