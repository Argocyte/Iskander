"""
Iskander API client for Streamlit.
Thin httpx wrapper — all calls go to the local FastAPI node.
"""

from __future__ import annotations

from typing import Any

import httpx

API_BASE = "http://localhost:8000"
TIMEOUT  = 30.0


def _get(path: str, params: dict | None = None) -> dict[str, Any]:
    with httpx.Client(base_url=API_BASE, timeout=TIMEOUT) as c:
        r = c.get(path, params=params)
        r.raise_for_status()
        return r.json()


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(base_url=API_BASE, timeout=TIMEOUT) as c:
        r = c.post(path, json=body)
        r.raise_for_status()
        return r.json()


# ── Health ────────────────────────────────────────────────────────────────────

def health() -> dict[str, Any]:
    return _get("/health")


# ── Constitution ──────────────────────────────────────────────────────────────

def get_constitution_template() -> dict[str, Any]:
    return _get("/constitution/template")


def generate_constitution(profile: dict[str, Any]) -> dict[str, Any]:
    return _post("/constitution/generate", profile)


# ── Governance ────────────────────────────────────────────────────────────────

def submit_proposal(payload: dict[str, Any]) -> dict[str, Any]:
    return _post("/governance/propose", payload)


def get_proposal(thread_id: str) -> dict[str, Any]:
    return _get(f"/governance/proposals/{thread_id}")


def cast_vote(payload: dict[str, Any]) -> dict[str, Any]:
    return _post("/governance/vote", payload)


# ── Inventory ─────────────────────────────────────────────────────────────────

def get_inventory() -> dict[str, Any]:
    """Directly invoke the inventory agent via a future endpoint stub."""
    try:
        return _get("/inventory/report")
    except Exception:
        return {"iskander:summary": "_Inventory endpoint not yet wired (Phase 5 stub)._", "vf:inventoryReport": []}
