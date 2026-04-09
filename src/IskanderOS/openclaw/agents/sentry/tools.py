"""
Sentry agent tool implementations.

The Sentry reads infrastructure health metrics and posts alerts to #ops.
It never modifies any service, configuration, or access control.

Tool categories:
  - glass_box_log           — audit trail (write actions only)
  - sentry_get_*            — read operations (no Glass Box required)
  - sentry_post_ops_alert   — write to Mattermost #ops (Glass Box required first)

Thread safety: all HTTP calls use per-request httpx.Client instances.

Alert thresholds are configurable via environment variables with safe defaults.
Threshold names: SENTRY_THRESHOLD_CPU, SENTRY_THRESHOLD_MEMORY,
SENTRY_THRESHOLD_DISK, SENTRY_THRESHOLD_BACKUP_HOURS,
SENTRY_THRESHOLD_PG_POOL, SENTRY_THRESHOLD_PG_LAG_SECONDS.

<!-- contributor: 7b3f9e2a-14c8-4d6a-8f05-c2e1a3d90b47 | feature/sentry-agent -->
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MATTERMOST_BASE = os.environ["MATTERMOST_URL"].rstrip("/")
MATTERMOST_BOT_TOKEN = os.environ["MATTERMOST_BOT_TOKEN"]
OPS_CHANNEL_ID = os.environ["MATTERMOST_OPS_CHANNEL_ID"]
GLASS_BOX_BASE = os.environ.get("GLASS_BOX_URL", "http://decision-recorder:3000")
BESZEL_BASE = os.environ.get("BESZEL_URL", "http://beszel:8090")
BESZEL_API_KEY = os.environ.get("BESZEL_API_KEY", "")
BACKREST_BASE = os.environ.get("BACKREST_URL", "http://backrest:9898")
IPFS_BASE = os.environ.get("IPFS_API_URL", "http://ipfs:5001")
PG_HEALTH_BASE = os.environ.get("PG_HEALTH_URL", "http://decision-recorder:3000")

_TIMEOUT = float(os.environ.get("SENTRY_HTTP_TIMEOUT", "15"))

# Alert thresholds — configurable, with safe defaults
_T_CPU = int(os.environ.get("SENTRY_THRESHOLD_CPU", "80"))
_T_MEMORY = int(os.environ.get("SENTRY_THRESHOLD_MEMORY", "85"))
_T_DISK = int(os.environ.get("SENTRY_THRESHOLD_DISK", "80"))
_T_BACKUP_HOURS = int(os.environ.get("SENTRY_THRESHOLD_BACKUP_HOURS", "25"))
_T_PG_POOL = int(os.environ.get("SENTRY_THRESHOLD_PG_POOL", "90"))
_T_PG_LAG = int(os.environ.get("SENTRY_THRESHOLD_PG_LAG_SECONDS", "60"))


def _http_client() -> httpx.Client:
    return httpx.Client(timeout=_TIMEOUT)


# ---------------------------------------------------------------------------
# Glass Box
# ---------------------------------------------------------------------------

def glass_box_log(
    *,
    actor_user_id: str,
    action: str,
    target: str,
    reasoning: str,
) -> dict[str, Any]:
    """
    Record a Sentry action in the Glass Box audit trail.
    Must be called BEFORE sentry_post_ops_alert.
    """
    payload = {
        "actor": actor_user_id,
        "agent": "sentry",
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
# Beszel — system metrics (read only)
# ---------------------------------------------------------------------------

def sentry_get_beszel_metrics() -> dict[str, Any]:
    """
    Return current system metrics from Beszel for all monitored hosts.

    Includes CPU, memory, disk, and network per host. Flags any metrics
    that exceed alert thresholds.
    """
    headers = {}
    if BESZEL_API_KEY:
        headers["Authorization"] = f"Bearer {BESZEL_API_KEY}"

    with _http_client() as client:
        resp = client.get(f"{BESZEL_BASE}/api/collections/systems/records", headers=headers)
        resp.raise_for_status()
        systems_data = resp.json()

    hosts = []
    alerts = []

    for system in systems_data.get("items", []):
        host_name = system.get("name", "unknown")
        stats = system.get("stats", {})

        cpu_pct = stats.get("cpu", 0)
        mem_pct = stats.get("mp", 0)   # memory percent
        disk_pct = stats.get("dp", 0)  # disk percent

        host = {
            "name": host_name,
            "status": system.get("status", "unknown"),
            "cpu_percent": cpu_pct,
            "memory_percent": mem_pct,
            "disk_percent": disk_pct,
            "network_sent_mb": round(stats.get("ns", 0) / 1_048_576, 2),
            "network_recv_mb": round(stats.get("nr", 0) / 1_048_576, 2),
            "updated": system.get("updated"),
        }
        hosts.append(host)

        if cpu_pct > _T_CPU:
            alerts.append(f"{host_name}: CPU at {cpu_pct}% (threshold {_T_CPU}%)")
        if mem_pct > _T_MEMORY:
            alerts.append(f"{host_name}: memory at {mem_pct}% (threshold {_T_MEMORY}%)")
        if disk_pct > _T_DISK:
            alerts.append(f"{host_name}: disk at {disk_pct}% (threshold {_T_DISK}%)")

    return {
        "hosts": hosts,
        "thresholds": {
            "cpu_percent": _T_CPU,
            "memory_percent": _T_MEMORY,
            "disk_percent": _T_DISK,
        },
        "alerts": alerts,
        "healthy": len(alerts) == 0,
    }


# ---------------------------------------------------------------------------
# Backrest — backup status (read only)
# ---------------------------------------------------------------------------

def sentry_get_backrest_status() -> dict[str, Any]:
    """
    Return Backrest backup repository status.

    Reports last successful backup time, next scheduled run, and any errors.
    Flags if the most recent successful backup is older than the threshold.
    """
    with _http_client() as client:
        resp = client.get(f"{BACKREST_BASE}/api/v1/operations?limit=20")
        resp.raise_for_status()
        ops_data = resp.json()

    operations = ops_data.get("operations", [])

    last_success: datetime | None = None
    last_error: str | None = None
    repos: dict[str, Any] = {}

    for op in operations:
        status = op.get("status", "")
        op_type = op.get("op", "")
        repo_id = op.get("repoId", "unknown")

        if op_type == "OPERATION_BACKUP":
            ts_str = op.get("unixTimeEndMs")
            if ts_str:
                ts = datetime.fromtimestamp(int(ts_str) / 1000, tz=timezone.utc)
                if status == "STATUS_SUCCESS":
                    if last_success is None or ts > last_success:
                        last_success = ts
                elif status == "STATUS_ERROR":
                    last_error = op.get("displayMessage", "unknown error")

            if repo_id not in repos:
                repos[repo_id] = {"last_backup": None, "status": status}

    now = datetime.now(timezone.utc)
    backup_age_hours: float | None = None
    alert = False

    if last_success:
        backup_age_hours = (now - last_success).total_seconds() / 3600
        alert = backup_age_hours > _T_BACKUP_HOURS
    else:
        alert = True  # No successful backup found at all

    return {
        "last_successful_backup": last_success.isoformat() if last_success else None,
        "backup_age_hours": round(backup_age_hours, 1) if backup_age_hours else None,
        "last_error": last_error,
        "repos": list(repos.keys()),
        "threshold_hours": _T_BACKUP_HOURS,
        "alert": alert,
        "healthy": not alert,
    }


# ---------------------------------------------------------------------------
# IPFS — pin integrity check (read only)
# ---------------------------------------------------------------------------

def sentry_check_ipfs_pins() -> dict[str, Any]:
    """
    Compare the IPFS pin count against the decision-recorder's expected count.

    A divergence means decisions may not be durably stored. Returns the
    expected count, actual pinned count, and any divergence.
    """
    # Get expected count from decision-recorder
    with _http_client() as client:
        dr_resp = client.get(f"{PG_HEALTH_BASE}/decisions/count")
        dr_resp.raise_for_status()
        expected = dr_resp.json().get("count", 0)

    # Get actual IPFS pin count
    with _http_client() as client:
        ipfs_resp = client.post(f"{IPFS_BASE}/api/v0/pin/ls?type=recursive")
        ipfs_resp.raise_for_status()
        # IPFS returns NDJSON; count the Keys
        pin_data = ipfs_resp.json()
        actual = len(pin_data.get("Keys", {}))

    divergence = abs(expected - actual)
    alert = divergence > 0

    return {
        "expected_count": expected,
        "pinned_count": actual,
        "divergence": divergence,
        "alert": alert,
        "healthy": not alert,
        "message": (
            f"{divergence} decision(s) may not be durably stored on IPFS."
            if alert else
            "All decisions are pinned on IPFS."
        ),
    }


# ---------------------------------------------------------------------------
# PostgreSQL — health check (read only, via decision-recorder endpoint)
# ---------------------------------------------------------------------------

def sentry_get_pg_health() -> dict[str, Any]:
    """
    Return PostgreSQL health metrics via the decision-recorder's /health endpoint.

    Reports connection pool utilisation and replication lag.
    Flags metrics that exceed alert thresholds.
    """
    with _http_client() as client:
        resp = client.get(f"{PG_HEALTH_BASE}/health/db")
        resp.raise_for_status()
        data = resp.json()

    pool_used = data.get("pool_used", 0)
    pool_size = data.get("pool_size", 1)
    pool_pct = round((pool_used / pool_size) * 100, 1) if pool_size else 0
    lag_seconds = data.get("replication_lag_seconds", 0)

    alerts = []
    if pool_pct > _T_PG_POOL:
        alerts.append(
            f"PostgreSQL connection pool at {pool_pct}% ({pool_used}/{pool_size}) "
            f"— threshold {_T_PG_POOL}%"
        )
    if lag_seconds > _T_PG_LAG:
        alerts.append(
            f"PostgreSQL replication lag {lag_seconds}s — threshold {_T_PG_LAG}s"
        )

    return {
        "pool_used": pool_used,
        "pool_size": pool_size,
        "pool_utilisation_percent": pool_pct,
        "replication_lag_seconds": lag_seconds,
        "thresholds": {
            "pool_percent": _T_PG_POOL,
            "lag_seconds": _T_PG_LAG,
        },
        "alerts": alerts,
        "healthy": len(alerts) == 0,
        "db_version": data.get("version"),
    }


# ---------------------------------------------------------------------------
# Mattermost — ops alert (write, Glass Box required first)
# ---------------------------------------------------------------------------

def sentry_post_ops_alert(
    *,
    actor_user_id: str,
    alert_text: str,
) -> dict[str, Any]:
    """
    Post an infrastructure alert to the #ops Mattermost channel.
    glass_box_log MUST be called before this.

    actor_user_id is "sentry-scheduler" for automated checks,
    or the requesting member's user ID for on-demand queries.
    """
    payload = {
        "channel_id": OPS_CHANNEL_ID,
        "message": alert_text,
        "props": {
            "from_agent": "sentry",
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
            "message_preview": alert_text[:120] + ("..." if len(alert_text) > 120 else ""),
        }


# ---------------------------------------------------------------------------
# Full health summary — composite read (no Glass Box required)
# ---------------------------------------------------------------------------

def sentry_get_full_health_summary() -> dict[str, Any]:
    """
    Run all health checks and return a combined summary.

    Used by scheduled checks and on-demand "how is the infrastructure?"
    queries. Each subsystem is checked independently — a failure in one
    does not block the others.
    """
    results: dict[str, Any] = {}
    errors: list[str] = []

    for check_name, check_fn in [
        ("beszel", sentry_get_beszel_metrics),
        ("backrest", sentry_get_backrest_status),
        ("ipfs", sentry_check_ipfs_pins),
        ("postgresql", sentry_get_pg_health),
    ]:
        try:
            results[check_name] = check_fn()
        except Exception as exc:
            logger.warning("Health check %s failed: %s", check_name, exc)
            results[check_name] = {"healthy": None, "error": str(exc)}
            errors.append(f"{check_name}: check failed ({exc})")

    all_alerts: list[str] = []
    for name, result in results.items():
        if result.get("healthy") is False:
            sub_alerts = result.get("alerts", [])
            if isinstance(sub_alerts, list):
                all_alerts.extend(sub_alerts)
            elif result.get("alert"):
                all_alerts.append(result.get("message", f"{name}: alert condition"))

    overall_healthy = len(all_alerts) == 0 and len(errors) == 0

    return {
        "healthy": overall_healthy,
        "subsystems": results,
        "alerts": all_alerts,
        "check_errors": errors,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "glass_box_log",
        "description": (
            "Record a Sentry action in the Glass Box audit trail. "
            "Call BEFORE sentry_post_ops_alert. Not required for read operations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "actor_user_id": {"type": "string", "description": "User ID or 'sentry-scheduler' for automated checks."},
                "action": {"type": "string", "description": "Short action identifier, e.g. 'post_ops_alert'."},
                "target": {"type": "string", "description": "What is being acted on, e.g. '#ops channel'."},
                "reasoning": {"type": "string", "description": "Why this alert is being posted."},
            },
            "required": ["actor_user_id", "action", "target", "reasoning"],
        },
    },
    {
        "name": "sentry_get_beszel_metrics",
        "description": (
            "Return current CPU, memory, disk, and network metrics from Beszel "
            "for all monitored hosts. Flags any metrics exceeding alert thresholds."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "sentry_get_backrest_status",
        "description": (
            "Return Backrest backup status: last successful run, age in hours, "
            "and any error messages. Flags if backup gap exceeds threshold."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "sentry_check_ipfs_pins",
        "description": (
            "Compare the IPFS pin count against the decision-recorder's expected count. "
            "Flags any divergence (decisions not durably stored)."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "sentry_get_pg_health",
        "description": (
            "Return PostgreSQL connection pool utilisation and replication lag. "
            "Flags metrics exceeding alert thresholds."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "sentry_get_full_health_summary",
        "description": (
            "Run all health checks (Beszel, Backrest, IPFS, PostgreSQL) and return "
            "a combined summary. Use this for scheduled checks and general 'how is "
            "the infrastructure?' queries."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "sentry_post_ops_alert",
        "description": (
            "Post an infrastructure alert to the #ops Mattermost channel. "
            "glass_box_log MUST be called first. "
            "For automated scheduled checks, actor_user_id should be 'sentry-scheduler'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "actor_user_id": {
                    "type": "string",
                    "description": "Member user ID or 'sentry-scheduler' for automated checks.",
                },
                "alert_text": {
                    "type": "string",
                    "description": "The alert message to post. Should be factual and specific.",
                },
            },
            "required": ["actor_user_id", "alert_text"],
        },
    },
]

TOOL_REGISTRY: dict[str, Any] = {
    "glass_box_log": glass_box_log,
    "sentry_get_beszel_metrics": sentry_get_beszel_metrics,
    "sentry_get_backrest_status": sentry_get_backrest_status,
    "sentry_check_ipfs_pins": sentry_check_ipfs_pins,
    "sentry_get_pg_health": sentry_get_pg_health,
    "sentry_get_full_health_summary": sentry_get_full_health_summary,
    "sentry_post_ops_alert": sentry_post_ops_alert,
}
