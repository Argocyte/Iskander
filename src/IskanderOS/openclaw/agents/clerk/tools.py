"""
Clerk agent tool implementations.

Each tool maps to a real API call. Before any tool that writes to external
systems, glass_box_log() MUST be called. This is enforced in agent.py.

Thread safety: all HTTP calls use per-request httpx.Client instances.
FastAPI serves concurrent requests in different threads; a shared client
can cause request mixing under concurrent load.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

import httpx

logger = logging.getLogger(__name__)

LOOMIO_BASE = os.environ["LOOMIO_URL"].rstrip("/")
LOOMIO_API_KEY = os.environ["LOOMIO_API_KEY"]
MATTERMOST_BASE = os.environ["MATTERMOST_URL"].rstrip("/")
MATTERMOST_BOT_TOKEN = os.environ["MATTERMOST_BOT_TOKEN"]
GLASS_BOX_BASE = os.environ.get("GLASS_BOX_URL", "http://decision-recorder:3000")
DECISION_RECORDER_BASE = os.environ.get("DECISION_RECORDER_URL", GLASS_BOX_BASE)
PROVISIONER_BASE = os.environ.get("PROVISIONER_URL", "http://provisioner:3001")
_INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")

# Configurable timeout — cooperative networks may have higher latency
_TIMEOUT = float(os.environ.get("CLERK_HTTP_TIMEOUT", "30"))

# Input validation limits
_MAX_TITLE_LEN = 200
_MAX_DESCRIPTION_LEN = 10_000


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
    with _http_client() as client:
        resp = client.post(f"{GLASS_BOX_BASE}/log", json=payload)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Provisioner — member onboarding across Authentik, Loomio, and Mattermost
# ---------------------------------------------------------------------------

def provision_member(
    *,
    username: str,
    email: str,
    display_name: str = "",
) -> dict[str, Any]:
    """
    Provision a new cooperative member across Authentik, Loomio, and Mattermost.
    Glass Box MUST be called before this function.
    Returns provisioning status including the password reset URL.
    """
    if len(username) > 128:
        raise ValueError("Username must be 128 characters or fewer.")
    if len(email) > 256:
        raise ValueError("Email must be 256 characters or fewer.")

    payload = {
        "username": username,
        "email": email,
        "display_name": display_name or username,
    }
    headers = {}
    if _INTERNAL_SERVICE_TOKEN:
        headers["Authorization"] = f"Bearer {_INTERNAL_SERVICE_TOKEN}"

    with _http_client() as client:
        resp = client.post(
            f"{PROVISIONER_BASE}/members",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Loomio — read operations (no Glass Box required)
# ---------------------------------------------------------------------------

def _loomio_get(path: str, params: dict | None = None) -> Any:
    with _http_client() as client:
        resp = client.get(
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
    with _http_client() as client:
        resp = client.post(
            f"{LOOMIO_BASE}/api/v1/{path}",
            json=payload,
            headers={"Authorization": f"Token {LOOMIO_API_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()


def _verify_group_membership(actor_user_id: str, group_key: str) -> None:
    """
    Verify the actor is a member of the target Loomio group.
    Raises ValueError if not a member, preventing cross-cooperative posting.
    """
    data = _loomio_get("memberships", {"actor_id": actor_user_id})
    member_groups = {
        m.get("group", {}).get("key")
        for m in data.get("memberships", [])
    }
    if group_key not in member_groups:
        raise ValueError(
            f"You are not a member of group '{group_key}'. "
            "Discussions can only be created in groups you belong to."
        )


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
    Verifies the actor is a member of the target group.
    """
    # Input validation
    if len(title) > _MAX_TITLE_LEN:
        raise ValueError(f"Title must be {_MAX_TITLE_LEN} characters or fewer.")
    if len(description) > _MAX_DESCRIPTION_LEN:
        raise ValueError(f"Description must be {_MAX_DESCRIPTION_LEN} characters or fewer.")
    if not title.strip():
        raise ValueError("Title cannot be empty.")

    # Verify the actor is a member of this group (prevents cross-cooperative posting)
    _verify_group_membership(actor_user_id, group_key)

    data = _loomio_post("discussions", {
        "discussion": {
            "group_key": group_key,
            "title": title.strip(),
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
    with _http_client() as client:
        resp = client.post(
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
    if len(message) > 16_383:  # Mattermost hard limit
        raise ValueError("Message too long. Split it into shorter messages.")
    data = _mm_post("posts", {"channel_id": channel_id, "message": message})
    return {"post_id": data["id"], "create_at": data["create_at"]}


# ---------------------------------------------------------------------------
# Decision Recorder — S3 governance tools (read operations: no Glass Box required)
# ---------------------------------------------------------------------------

def dr_list_due_reviews(days_ahead: int = 30) -> dict:
    """List agreements whose review date falls within the next N days."""
    with _http_client() as client:
        resp = client.get(
            f"{DECISION_RECORDER_BASE}/decisions/reviews/due",
            params={"days_ahead": days_ahead},
        )
        resp.raise_for_status()
        return resp.json()


def dr_list_tensions(
    status: str | None = None,
    domain: str | None = None,
    limit: int = 20,
) -> dict:
    """List logged organisational tensions."""
    params: dict = {"limit": limit}
    if status:
        params["status"] = status
    if domain:
        params["domain"] = domain
    with _http_client() as client:
        resp = client.get(f"{DECISION_RECORDER_BASE}/tensions", params=params)
        resp.raise_for_status()
        return resp.json()


def draft_driver_statement(
    *,
    situation: str,
    actor: str,
    need: str,
    consequence: str,
) -> str:
    """
    Format a well-structured S3 driver statement from four components.
    Returns formatted text only — no external API call.
    """
    return (
        f'**Driver statement**\n\n'
        f'"In the context of **{situation}**, **{actor}** needs **{need}** '
        f'in order to **{consequence}**."'
    )


# ---------------------------------------------------------------------------
# Decision Recorder — S3 governance tools (write operations: Glass Box required)
# ---------------------------------------------------------------------------

def dr_log_tension(
    *,
    description: str,
    actor_user_id: str,
    domain: str | None = None,
    driver_statement: str | None = None,
) -> dict:
    """
    Log an organisational tension (S3: Navigate Via Tension).
    Glass Box MUST be called before this function.
    """
    payload = {
        "description": description,
        "logged_by": actor_user_id,
        "domain": domain,
        "driver_statement": driver_statement,
    }
    with _http_client() as client:
        resp = client.post(f"{DECISION_RECORDER_BASE}/tensions", json=payload)
        resp.raise_for_status()
        return resp.json()


def dr_update_tension(
    *,
    tension_id: int,
    status: str | None = None,
    driver_statement: str | None = None,
    loomio_discussion_id: int | None = None,
) -> dict:
    """
    Update a tension's status, driver statement, or linked discussion.
    Glass Box MUST be called before this function when changing status.
    """
    payload: dict = {}
    if status:
        payload["status"] = status
    if driver_statement is not None:
        payload["driver_statement"] = driver_statement
    if loomio_discussion_id is not None:
        payload["loomio_discussion_id"] = loomio_discussion_id
    with _http_client() as client:
        resp = client.patch(f"{DECISION_RECORDER_BASE}/tensions/{tension_id}", json=payload)
        resp.raise_for_status()
        return resp.json()


def dr_set_review_date(
    *,
    decision_id: int,
    review_date: str,
    review_circle: str | None = None,
) -> dict:
    """
    Set a review date on a recorded agreement (S3: Evaluate and Evolve Agreements).
    Glass Box MUST be called before this function.
    review_date must be ISO 8601 format: YYYY-MM-DD.
    """
    payload: dict = {"review_date": review_date}
    if review_circle:
        payload["review_circle"] = review_circle
    with _http_client() as client:
        resp = client.patch(
            f"{DECISION_RECORDER_BASE}/decisions/{decision_id}/review",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Meeting prep tools — read-only, no Glass Box required
# ---------------------------------------------------------------------------

def list_recent_decisions(group_key: str | None = None, limit: int = 10) -> list[dict]:
    """
    List recently recorded cooperative decisions from the Glass Box.
    Returns a list of decision summaries (id, title, status, outcome,
    ipfs_cid, loomio_url, decided_at, recorded_at).
    """
    params: dict = {"limit": limit}
    if group_key is not None:
        params["group_key"] = group_key
    with _http_client() as client:
        resp = client.get(f"{GLASS_BOX_BASE}/decisions", params=params)
        resp.raise_for_status()
        return resp.json().get("decisions", [])


def list_due_reviews() -> list[dict]:
    """
    List cooperative agreements that are due for review (S3: Evolve Agreements).
    Returns the reviews list from the JSON response
    (id, title, outcome, review_due_at).
    """
    with _http_client() as client:
        resp = client.get(f"{GLASS_BOX_BASE}/decisions/reviews/due")
        resp.raise_for_status()
        return resp.json().get("reviews", [])


def list_tensions(limit: int = 10) -> list[dict]:
    """
    List organisational tensions logged by members (S3: Navigate Via Tension).
    Returns the tensions list (id, title, driver, status, created_at).
    """
    with _http_client() as client:
        resp = client.get(f"{GLASS_BOX_BASE}/tensions", params={"limit": limit})
        resp.raise_for_status()
        return resp.json().get("tensions", [])


def prepare_meeting_agenda(group_key: str | None = None) -> str:
    """
    Generate a draft meeting agenda from the Glass Box.

    Pulls:
    - Agreements due for review (list_due_reviews)
    - Open tensions (list_tensions, limit=10)
    - Recent decisions (list_recent_decisions, limit=5)

    Returns a formatted Markdown document ready to share.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    decisions = list_recent_decisions(group_key=group_key, limit=5)
    reviews = list_due_reviews()
    tensions = list_tensions(limit=10)

    lines: list[str] = [f"# Meeting Agenda — {today}", ""]

    # Section 1: Reviews
    lines.append("## 1. Agreements due for review")
    if reviews:
        for r in reviews:
            lines.append(f"- **{r.get('title', '(untitled)')}** — due {r.get('review_due_at', '?')}")
    else:
        lines.append("No agreements are due for review.")
    lines.append("")

    # Section 2: Tensions
    lines.append("## 2. Open tensions (navigator's log)")
    if tensions:
        for t in tensions:
            driver = t.get("driver") or ""
            driver_preview = driver[:100] + "..." if len(driver) > 100 else driver
            lines.append(f"- [{t.get('id', '?')}] **{t.get('title', '(untitled)')}** — {driver_preview}")
    else:
        lines.append("No open tensions logged.")
    lines.append("")

    # Section 3: Recent decisions
    lines.append("## 3. Recent decisions (last 5)")
    if decisions:
        for d in decisions:
            date_str = d.get("decided_at") or d.get("recorded_at") or "?"
            lines.append(f"- **{d.get('title', '(untitled)')}** ({d.get('status', '?')}) — {date_str}")
    else:
        lines.append("No recent decisions recorded.")
    lines.append("")

    lines.append("---")
    lines.append("*Generated by the Clerk. Review and add standing items before circulating.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Governance Health Signals — Phase 1 (5 signals computed from DR + Loomio)
# ---------------------------------------------------------------------------

# Pattern library is co-located with this file
_PATTERN_LIBRARY_PATH = Path(__file__).parent.parent.parent / "governance_patterns.yaml"

_LIFECYCLE_THRESHOLDS = {
    "founding": 15,   # members
    "growing": 30,
    "maturing": 50,
}

_NUDGE_TEMPLATES: dict[str, str] = {
    "SIG-05": (
        "Consent proposals have been blocked in {count} of your last 10 proposals. "
        "This is a common signal that proposals need more prior consultation before "
        "the consent question is asked — or that what counts as a valid objection "
        "needs clarifying.\n\n"
        "The pattern library has guidance on this: ask me to 'search patterns for SIG-05'."
    ),
    "SIG-06": (
        "{count} agreement(s) are overdue for review by more than 30 days. "
        "Zombie policies — agreements no one follows because no one remembered to update them "
        "— erode trust in formal governance.\n\n"
        "I can list the overdue reviews and help you schedule a governance session."
    ),
    "SIG-07": (
        "{count} tension(s) have been open for more than 14 days without being processed. "
        "Tensions that are logged but not acted on signal that governance meetings are not "
        "connecting to the tension backlog.\n\n"
        "Reserve 10 minutes at your next meeting to triage these. I can prepare a summary."
    ),
    "SIG-09": (
        "Your cooperative has {count} members — a size where many cooperatives find that "
        "delegating some decisions to smaller circles makes governance more manageable.\n\n"
        "A common starting point: one Finance or Operations circle with spending authority "
        "up to a defined threshold, leaving everything else with the full membership. "
        "I can help draft a circle charter if you'd like to explore it."
    ),
    "SIG-11": (
        "More than 90% of your recent decisions have passed with no abstentions or objections. "
        "This may simply mean your proposals are well-prepared — but it can also signal "
        "that substantive deliberation is happening informally, outside the formal process.\n\n"
        "Consider checking whether members feel safe to object. The pattern library has guidance."
    ),
}


def _get_loomio_member_count(group_key: str | None) -> int | None:
    """Fetch member count from Loomio groups API. Returns None on error."""
    try:
        path = "groups"
        params: dict = {}
        if group_key:
            params["key"] = group_key
        data = _loomio_get(path, params)
        groups = data if isinstance(data, list) else data.get("groups", [])
        if not groups:
            return None
        # Sum member counts across matching groups
        return sum(g.get("memberships_count", 0) for g in groups[:1])  # first group only
    except Exception:
        logger.warning("Could not fetch Loomio member count", exc_info=True)
        return None


def assess_governance_health(group_key: str | None = None) -> dict:
    """
    Run a Phase 1 governance health assessment and store the report.

    Checks 5 signals computable from existing data:
      SIG-05: Block rate spike (decision-recorder)
      SIG-06: Governance debt (decision-recorder)
      SIG-07: Tension backlog (decision-recorder)
      SIG-09: Structural scale threshold (Loomio)
      SIG-11: Unanimous voting pattern (decision-recorder)

    Stores the report via POST /governance/health-reports and returns it.
    Glass Box MUST be called before this function (write action).
    """
    signals: list[dict] = []
    nudges: list[dict] = []

    # --- Fetch raw data ---
    try:
        with _http_client() as client:
            # Last 10 decisions for block rate and unanimity checks
            decisions_resp = client.get(
                f"{DECISION_RECORDER_BASE}/decisions",
                params={"limit": 10, **({"group_key": group_key} if group_key else {})},
            )
            decisions_resp.raise_for_status()
            recent_decisions = decisions_resp.json().get("decisions", [])

            # Overdue reviews
            reviews_resp = client.get(
                f"{DECISION_RECORDER_BASE}/decisions/reviews/due",
                params={"days_ahead": 0},  # only already-overdue
            )
            reviews_resp.raise_for_status()
            overdue_reviews = reviews_resp.json().get("reviews", [])

            # Stale tensions
            tensions_resp = client.get(
                f"{DECISION_RECORDER_BASE}/tensions",
                params={"status": "open", "limit": 50},
            )
            tensions_resp.raise_for_status()
            open_tensions = tensions_resp.json().get("tensions", [])
    except Exception as exc:
        raise RuntimeError(f"Could not fetch data for health assessment: {exc}") from exc

    today = date.today()

    # --- SIG-05: Block rate spike ---
    blocked = [d for d in recent_decisions if d.get("status") == "blocked"]
    if len(blocked) >= 3:
        sig = {
            "id": "SIG-05",
            "name": "Block rate spike",
            "severity": "warning",
            "detected": True,
            "detail": f"{len(blocked)} of last {len(recent_decisions)} proposals were blocked",
        }
        signals.append(sig)
        nudges.append({
            "id": "NUDGE-SIG-05",
            "signal_id": "SIG-05",
            "message": _NUDGE_TEMPLATES["SIG-05"].format(count=len(blocked)),
            "actions": ["search_pattern_library('SIG-05')", "dr_list_tensions()"],
        })
    else:
        signals.append({
            "id": "SIG-05", "name": "Block rate spike",
            "severity": "warning", "detected": False, "detail": f"{len(blocked)} blocked in last {len(recent_decisions)}",
        })

    # --- SIG-06: Governance debt ---
    # Overdue reviews: review_date < today AND review_status != "complete"
    debt_count = 0
    for r in overdue_reviews:
        due = r.get("review_due_at") or r.get("review_date")
        if due:
            try:
                due_date = date.fromisoformat(str(due)[:10])
                days_overdue = (today - due_date).days
                if days_overdue > 30:
                    debt_count += 1
            except (ValueError, TypeError):
                pass
    if debt_count >= 5:
        signals.append({
            "id": "SIG-06", "name": "Governance debt",
            "severity": "advisory", "detected": True,
            "detail": f"{debt_count} agreements overdue for review by >30 days",
        })
        nudges.append({
            "id": "NUDGE-SIG-06",
            "signal_id": "SIG-06",
            "message": _NUDGE_TEMPLATES["SIG-06"].format(count=debt_count),
            "actions": ["dr_list_due_reviews(days_ahead=0)"],
        })
    else:
        signals.append({
            "id": "SIG-06", "name": "Governance debt",
            "severity": "advisory", "detected": False,
            "detail": f"{debt_count} agreements overdue by >30 days (threshold: 5)",
        })

    # --- SIG-07: Tension backlog ---
    stale_tensions = 0
    for t in open_tensions:
        logged_at = t.get("logged_at")
        if logged_at:
            try:
                logged = datetime.fromisoformat(str(logged_at).replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - logged).days
                if age_days > 14:
                    stale_tensions += 1
            except (ValueError, TypeError):
                pass
    if stale_tensions >= 8:
        signals.append({
            "id": "SIG-07", "name": "Tension backlog",
            "severity": "advisory", "detected": True,
            "detail": f"{stale_tensions} tensions open for >14 days",
        })
        nudges.append({
            "id": "NUDGE-SIG-07",
            "signal_id": "SIG-07",
            "message": _NUDGE_TEMPLATES["SIG-07"].format(count=stale_tensions),
            "actions": ["dr_list_tensions(status='open')"],
        })
    else:
        signals.append({
            "id": "SIG-07", "name": "Tension backlog",
            "severity": "advisory", "detected": False,
            "detail": f"{stale_tensions} tensions open for >14 days (threshold: 8)",
        })

    # --- SIG-09: Structural scale threshold ---
    member_count = _get_loomio_member_count(group_key)
    if member_count is not None:
        threshold_crossed = None
        for threshold in (50, 30, 15):
            if member_count >= threshold:
                threshold_crossed = threshold
                break
        if threshold_crossed:
            signals.append({
                "id": "SIG-09", "name": "Structural scale threshold",
                "severity": "advisory", "detected": True,
                "detail": f"{member_count} members — crossed {threshold_crossed}-member threshold",
            })
            nudges.append({
                "id": "NUDGE-SIG-09",
                "signal_id": "SIG-09",
                "message": _NUDGE_TEMPLATES["SIG-09"].format(count=member_count),
                "actions": ["search_pattern_library('SIG-09')"],
            })
        else:
            signals.append({
                "id": "SIG-09", "name": "Structural scale threshold",
                "severity": "advisory", "detected": False,
                "detail": f"{member_count} members (thresholds: 15/30/50)",
            })

    # --- SIG-11: Unanimous voting pattern ---
    decisions_with_stances = [
        d for d in recent_decisions
        if d.get("stance_counts") and isinstance(d["stance_counts"], dict)
    ]
    if decisions_with_stances:
        unanimous = sum(
            1 for d in decisions_with_stances
            if sum(v for k, v in d["stance_counts"].items() if k not in ("agree", "abstain")) == 0
        )
        unanimity_rate = unanimous / len(decisions_with_stances)
        if unanimity_rate > 0.9:
            signals.append({
                "id": "SIG-11", "name": "Unanimous voting pattern",
                "severity": "advisory", "detected": True,
                "detail": f"{unanimous}/{len(decisions_with_stances)} recent decisions had no objections",
            })
            nudges.append({
                "id": "NUDGE-SIG-11",
                "signal_id": "SIG-11",
                "message": _NUDGE_TEMPLATES["SIG-11"],
                "actions": ["search_pattern_library('SIG-11')"],
            })
        else:
            signals.append({
                "id": "SIG-11", "name": "Unanimous voting pattern",
                "severity": "advisory", "detected": False,
                "detail": f"{unanimity_rate:.0%} unanimous (threshold: >90%)",
            })

    # --- Lifecycle stage inference ---
    lifecycle_stage: str | None = None
    if member_count is not None:
        if member_count >= 50:
            lifecycle_stage = "scaling"
        elif member_count >= 15:
            lifecycle_stage = "growing"
        else:
            lifecycle_stage = "founding"

    # --- Store report ---
    report_payload = {
        "lifecycle_stage": lifecycle_stage,
        "signals": signals,
        "nudges": nudges,
    }
    with _http_client() as client:
        resp = client.post(
            f"{DECISION_RECORDER_BASE}/governance/health-reports",
            json=report_payload,
        )
        resp.raise_for_status()
        stored = resp.json()

    detected = [s for s in signals if s.get("detected")]
    return {
        "report_id": stored["id"],
        "assessed_at": stored["assessed_at"],
        "lifecycle_stage": lifecycle_stage,
        "signals_detected": len(detected),
        "signals": signals,
        "nudges": nudges,
        "summary": (
            f"Assessment complete. {len(detected)} signal(s) detected out of {len(signals)} checked."
            + (" Nudges have been generated — ask me to explain any of them." if nudges else "")
        ),
    }


def get_governance_health_report() -> dict:
    """Fetch the most recent governance health report from the decision-recorder."""
    with _http_client() as client:
        resp = client.get(f"{DECISION_RECORDER_BASE}/governance/health-reports/latest")
        if resp.status_code == 404:
            return {"error": "No health report found. Run 'assess_governance_health' first."}
        resp.raise_for_status()
        return resp.json()


def search_pattern_library(query: str, signal_id: str | None = None) -> list[dict]:
    """
    Search the local governance pattern library.

    The pattern library contains curated cooperative governance failure modes
    and proven responses, drawn from ICA guidance, Radical Routes, and S3.

    Returns matching patterns as a list of dicts with id, title, description,
    what_helps, what_doesnt_help, and references.
    """
    try:
        with open(_PATTERN_LIBRARY_PATH) as f:
            data = yaml.safe_load(f)
        patterns = data.get("patterns", [])
    except (FileNotFoundError, yaml.YAMLError) as exc:
        logger.warning("Could not load pattern library: %s", exc)
        return []

    query_lower = query.lower()
    results = []
    for pat in patterns:
        # Filter by signal_id if provided
        if signal_id and signal_id not in (pat.get("signals") or []):
            continue
        # Text match: check title and description
        if (
            query_lower in pat.get("title", "").lower()
            or query_lower in pat.get("description", "").lower()
            or query_lower in " ".join(pat.get("signals", [])).lower()
        ):
            results.append({
                "id": pat["id"],
                "title": pat["title"],
                "signals": pat.get("signals", []),
                "description": pat.get("description", "").strip(),
                "what_helps": pat.get("what_helps", []),
                "what_doesnt_help": pat.get("what_doesnt_help", []),
                "references": pat.get("references", []),
            })
    return results


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
        "name": "dr_list_due_reviews",
        "description": (
            "List cooperative agreements whose review date is approaching. "
            "Use this to surface agreements that need the circle's attention — "
            "especially useful when a member asks 'what decisions are due for review?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "Look ahead this many days (default 30, max 365)"},
            },
        },
    },
    {
        "name": "dr_list_tensions",
        "description": (
            "List organisational tensions that members have logged. "
            "Tensions are gaps between current reality and what could be — "
            "the raw material for driver statements and proposals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["open", "in_progress", "resolved"], "description": "Filter by status (omit for all)"},
                "domain": {"type": "string", "description": "Filter by circle or domain"},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
        },
    },
    {
        "name": "draft_driver_statement",
        "description": (
            "Format a well-structured S3 driver statement from four components. "
            "Use this when a member wants to articulate a tension as a driver. "
            "Returns formatted text only — does not post or save anything."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "situation": {"type": "string", "description": "Current state of affairs — what is actually happening now"},
                "actor": {"type": "string", "description": "Who experiences the need — a role, circle, or the cooperative as a whole"},
                "need": {"type": "string", "description": "What capability or condition is missing (not a solution)"},
                "consequence": {"type": "string", "description": "What becomes possible, or what harm is avoided"},
            },
            "required": ["situation", "actor", "need", "consequence"],
        },
    },
    {
        "name": "dr_log_tension",
        "description": (
            "Log an organisational tension to the decision recorder. "
            "REQUIRES glass_box_log to be called first. "
            "Use when a member describes a gap between current reality and what could be."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "What the member noticed — the raw tension"},
                "domain": {"type": "string", "description": "Which circle or area this relates to (optional)"},
                "driver_statement": {"type": "string", "description": "Formatted S3 driver statement (optional — can be added later)"},
            },
            "required": ["description"],
        },
    },
    {
        "name": "dr_update_tension",
        "description": (
            "Update the status or driver statement of a logged tension. "
            "REQUIRES glass_box_log when changing status. "
            "Use when a tension has been addressed or linked to a Loomio discussion."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tension_id": {"type": "integer", "description": "Tension ID from dr_log_tension or dr_list_tensions"},
                "status": {"type": "string", "enum": ["open", "in_progress", "resolved"]},
                "driver_statement": {"type": "string", "description": "Updated S3 driver statement"},
                "loomio_discussion_id": {"type": "integer", "description": "ID of the discussion this tension became"},
            },
            "required": ["tension_id"],
        },
    },
    {
        "name": "dr_set_review_date",
        "description": (
            "Set a review date on a recorded agreement (S3: Evaluate and Evolve Agreements). "
            "REQUIRES glass_box_log to be called first. "
            "Use after a decision is made, or when a member asks to schedule a review."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "decision_id": {"type": "integer", "description": "Decision ID from the recorded decisions"},
                "review_date": {"type": "string", "description": "Review date in YYYY-MM-DD format"},
                "review_circle": {"type": "string", "description": "Loomio group key responsible for initiating the review"},
            },
            "required": ["decision_id", "review_date"],
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
    # Meeting prep tools — read-only
    {
        "name": "list_recent_decisions",
        "description": "List recently recorded cooperative decisions from the Glass Box.",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_key": {"type": "string", "description": "Optional: filter by Loomio group key"},
                "limit": {"type": "integer", "description": "Max results (default 10, max 50)"},
            },
        },
    },
    {
        "name": "list_due_reviews",
        "description": "List cooperative agreements that are due for review (S3: Evolve Agreements).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_tensions",
        "description": "List organisational tensions logged by members (S3: Navigate Via Tension).",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "prepare_meeting_agenda",
        "description": (
            "Generate a draft meeting agenda from the Glass Box: "
            "agreements due for review, open tensions, and recent decisions. "
            "Returns a formatted Markdown document ready to share."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "group_key": {"type": "string", "description": "Optional: filter decisions by Loomio group key"},
            },
        },
    },
    {
        "name": "provision_member",
        "description": (
            "Provision a new cooperative member across Authentik SSO, Loomio, and Mattermost. "
            "REQUIRES glass_box_log to be called first. "
            "REQUIRES explicit member confirmation before calling. "
            "Returns a password reset URL to share with the new member."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Lowercase username (letters, numbers, hyphens, underscores only)"},
                "email": {"type": "string", "description": "New member's email address"},
                "display_name": {"type": "string", "description": "Display name (optional, defaults to username)"},
            },
            "required": ["username", "email"],
        },
    },
    # Governance health signals — Phase 1 (5 signals)
    {
        "name": "assess_governance_health",
        "description": (
            "Run a governance health assessment and store the report. "
            "Checks 5 observable signals: block rate spike, governance debt, "
            "tension backlog, structural scale threshold, and unanimous voting pattern. "
            "REQUIRES glass_box_log to be called first (this is a write action — it stores a report). "
            "Returns detected signals and nudges. Use monthly or when a member asks about "
            "governance health."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "group_key": {
                    "type": "string",
                    "description": "Loomio group key to scope the assessment (optional — omit for all groups)",
                },
            },
        },
    },
    {
        "name": "get_governance_health_report",
        "description": (
            "Retrieve the most recent governance health report. "
            "Read-only — no Glass Box required. "
            "Use when a member asks 'how is our governance doing?' or 'what did the last health check find?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "search_pattern_library",
        "description": (
            "Search the governance pattern library for known failure modes and proven responses. "
            "Read-only — no Glass Box required. "
            "Use when a member wants to understand a signal, or asks for governance advice. "
            "The library draws from ICA guidance, Radical Routes, and S3 Practical Guide."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term — can be a signal ID (e.g. 'SIG-05'), a keyword, or a description of the governance challenge",
                },
                "signal_id": {
                    "type": "string",
                    "description": "Optional: filter to patterns for a specific signal (e.g. 'SIG-06')",
                },
            },
            "required": ["query"],
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
    "provision_member": provision_member,
    # S3 governance tools
    "dr_list_due_reviews": dr_list_due_reviews,
    "dr_list_tensions": dr_list_tensions,
    "draft_driver_statement": draft_driver_statement,
    "dr_log_tension": dr_log_tension,
    "dr_update_tension": dr_update_tension,
    "dr_set_review_date": dr_set_review_date,
    # Meeting prep tools
    "list_recent_decisions": list_recent_decisions,
    "list_due_reviews": list_due_reviews,
    "list_tensions": list_tensions,
    "prepare_meeting_agenda": prepare_meeting_agenda,
    # Governance health signals
    "assess_governance_health": assess_governance_health,
    "get_governance_health_report": get_governance_health_report,
    "search_pattern_library": search_pattern_library,
}
