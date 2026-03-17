"""
/procurement — Cooperative-first supply chain sourcing.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.library.procurement import procurement_graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/procurement", tags=["procurement"])


# ── Request / Response schemas ────────────────────────────────────────────────


class PurchaseRequest(BaseModel):
    description: str = Field(..., min_length=1, description="Natural-language purchase request.")


class PurchaseResponse(BaseModel):
    vendor: dict[str, Any] | None = None
    rea_order: dict[str, Any] | None = None
    vendor_candidates: list[dict[str, Any]] = []
    action_log: list[dict[str, Any]] = []
    error: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/purchase", response_model=PurchaseResponse)
async def create_purchase(req: PurchaseRequest):
    """Run the procurement pipeline and return a REA-formatted order."""
    initial_state = {
        "messages": [],
        "agent_id": "procurement-agent-v1",
        "action_log": [],
        "error": None,
        "purchase_request": {"description": req.description},
        "vendor_candidates": [],
        "selected_vendor": None,
        "rea_order": None,
    }

    try:
        result = procurement_graph.invoke(initial_state)
    except Exception as exc:
        logger.exception("Procurement agent failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    return PurchaseResponse(
        vendor=result.get("selected_vendor"),
        rea_order=result.get("rea_order"),
        vendor_candidates=result.get("vendor_candidates", []),
        action_log=result.get("action_log", []),
    )


@router.get("/vendors")
async def list_vendors():
    """Return the known cooperative vendor registry (stub)."""
    from backend.agents.library.procurement import _STUB_COOPERATIVE_VENDORS
    return {"vendors": _STUB_COOPERATIVE_VENDORS}
