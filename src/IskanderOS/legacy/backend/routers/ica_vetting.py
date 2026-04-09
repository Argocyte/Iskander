"""
/ica-vetting — ICA Ethics Vetting Agent endpoints (Phase 17).

Evaluate potential trading partners against the 7 ICA Cooperative Principles.
The agent assesses; the cooperative's democratic body decides.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.library.ica_vetter import ica_vetter_graph, ICA_PRINCIPLES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ica-vetting", tags=["ica-vetting"])


# ── Request / Response schemas ────────────────────────────────────────────────


class CandidatePartner(BaseModel):
    """A potential trading partner to vet."""
    name: str = Field(..., description="Human-readable name of the candidate.")
    type: str = Field(
        default="unknown",
        description="Entity type: cooperative, worker-cooperative, social-enterprise, conventional, unknown.",
    )
    did: str | None = Field(None, description="DID or Ethereum address (for on-chain lookup).")
    address: str | None = Field(None, description="Ethereum address if no DID.")
    sector: str | None = Field(None, description="Candidate's primary sector.")
    info: dict[str, Any] = Field(
        default_factory=dict,
        description="Any additional known information about the candidate.",
    )


class VettingRequest(BaseModel):
    """Request to vet one or more trading partners."""
    sector: str = Field(..., description="Sector need driving this vetting (e.g., 'organic grain supply').")
    candidates: list[CandidatePartner] = Field(
        ..., min_length=1,
        description="One or more candidate partners to assess.",
    )
    principle_weights: dict[str, float] | None = Field(
        None,
        description="Optional per-principle weights (P1-P7). Defaults to equal weighting.",
    )


class VettingResponse(BaseModel):
    """Vetting results: value matrix + detailed assessments."""
    report_id: str
    sector: str
    candidate_count: int
    value_matrix: dict[str, Any] | None = None
    detailed_assessments: list[dict[str, Any]] = []
    executive_summary: str = ""
    action_log: list[dict[str, Any]] = []
    requires_human_review: bool = False
    error: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/assess", response_model=VettingResponse)
async def assess_trading_partners(req: VettingRequest):
    """Run the ICA Ethics Vetting pipeline against candidate trading partners.

    Returns a ranked value matrix scoring each candidate on all 7 ICA
    Cooperative Principles, with per-principle evidence, grades, and
    plain-language summaries.

    If any candidate scores FAIL on any principle, the response sets
    `requires_human_review=True` — the cooperative must explicitly approve
    before proceeding with that partner.
    """
    # Build candidate dicts from request.
    candidates = []
    for c in req.candidates:
        candidate = {
            "name": c.name,
            "type": c.type,
            "did": c.did,
            "address": c.address,
            "sector": c.sector,
            **c.info,
        }
        candidates.append(candidate)

    initial_state = {
        "messages": [],
        "agent_id": "ica-vetter-agent-v1",
        "action_log": [],
        "error": None,
        "partner_query": {
            "sector": req.sector,
            "candidates": candidates,
            "principle_weights": req.principle_weights,
        },
        "candidate_partners": [],
        "on_chain_signals": [],
        "off_chain_signals": [],
        "principle_assessments": [],
        "value_matrix": None,
        "vetting_report": None,
        "requires_human_token": False,
    }

    try:
        result = ica_vetter_graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": str(uuid4())}},
        )
    except Exception as exc:
        logger.exception("ICA vetting agent failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    report = result.get("vetting_report", {}) or {}

    return VettingResponse(
        report_id=report.get("report_id", str(uuid4())),
        sector=req.sector,
        candidate_count=len(candidates),
        value_matrix=report.get("value_matrix"),
        detailed_assessments=report.get("detailed_assessments", []),
        executive_summary=report.get("executive_summary", ""),
        action_log=result.get("action_log", []),
        requires_human_review=result.get("requires_human_token", False),
    )


@router.get("/principles")
async def list_ica_principles():
    """Return the 7 ICA Cooperative Principles used for assessment."""
    return {"principles": ICA_PRINCIPLES}
