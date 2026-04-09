"""
arbitration.py — Phase 15: Solidarity Court API Router.

Endpoints:
  POST /arbitration/disputes                  — File a new dispute.
  GET  /arbitration/disputes/{id}             — Get dispute status.
  POST /arbitration/disputes/{id}/evidence    — Submit additional evidence.
  POST /arbitration/disputes/{id}/verdict     — Record jury verdict (operator only).
  GET  /arbitration/disputes/{id}/jury        — Get jury member list.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from backend.agents.library.arbitrator import arbitrator_graph
from backend.auth.dependencies import AuthenticatedUser, get_current_user, require_role
from backend.schemas.arbitration import DisputeCreate, EvidenceSubmission, Verdict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/arbitration", tags=["arbitration"])

# STUB: in-memory case registry. Replace with asyncpg in production.
_cases: dict[str, dict[str, Any]] = {}
_thread_counter = 0


def _next_thread() -> str:
    global _thread_counter
    _thread_counter += 1
    return f"arbitrator-{_thread_counter}"


# ── POST /arbitration/disputes ────────────────────────────────────────────────

@router.post("/disputes", status_code=status.HTTP_202_ACCEPTED)
async def file_dispute(
    body: DisputeCreate,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    File a new arbitration dispute.

    Starts the Arbitrator LangGraph. Suspends at `human_jury_deliberation`.
    """
    case_id = str(uuid.uuid4())
    thread_id = _next_thread()
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [],
        "agent_id": (AGENT_ID := "arbitrator-agent-v1"),
        "action_log": [],
        "error": None,
        "dispute": {**body.model_dump(), "case_id": case_id},
        "evidence": body.evidence_cids,
        "jury_pool": [],
        "jury_selected": [],
        "verdict": None,
        "escrow_id": body.escrow_id,
        "remedy_executed": False,
        "requires_human_token": False,
        "case_id": case_id,
    }

    try:
        final = arbitrator_graph.invoke(initial_state, config=config)
    except Exception as exc:
        logger.exception("Arbitrator graph error for case %s", case_id)
        raise HTTPException(status_code=500, detail=str(exc))

    if final.get("error"):
        raise HTTPException(status_code=422, detail=final["error"])

    _cases[case_id] = {
        "case_id": case_id,
        "thread_id": thread_id,
        "status": "jury_selection" if final.get("jurisdiction") == "inter_coop" else "deliberation",
        "dispute": body.model_dump(),
        "jury_selected": final.get("jury_selected", []),
        "verdict": None,
        "remedy_executed": False,
    }

    return {
        "case_id": case_id,
        "status": _cases[case_id]["status"],
        "jury_selected": len(final.get("jury_selected", [])),
        "message": (
            "Dispute filed. Federated jury selection initiated. "
            "Jury will deliberate via Matrix rooms. "
            f"Vote endpoint: POST /arbitration/disputes/{case_id}/verdict"
        ),
    }


# ── GET /arbitration/disputes/{id} ───────────────────────────────────────────

@router.get("/disputes/{case_id}", status_code=status.HTTP_200_OK)
async def get_dispute(case_id: str) -> dict[str, Any]:
    c = _cases.get(case_id)
    if not c:
        raise HTTPException(status_code=404, detail="Case not found.")
    return c


# ── POST /arbitration/disputes/{id}/evidence ─────────────────────────────────

@router.post("/disputes/{case_id}/evidence", status_code=status.HTTP_200_OK)
async def submit_evidence(
    case_id: str,
    body: EvidenceSubmission,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    c = _cases.get(case_id)
    if not c:
        raise HTTPException(status_code=404, detail="Case not found.")
    if c["status"] not in ("jury_selection", "deliberation"):
        raise HTTPException(status_code=409, detail="Evidence submission not open.")

    c["dispute"].setdefault("evidence_cids", []).append(body.ipfs_cid)
    return {"case_id": case_id, "evidence_cid": body.ipfs_cid, "accepted": True}


# ── POST /arbitration/disputes/{id}/verdict ───────────────────────────────────

@router.post("/disputes/{case_id}/verdict", status_code=status.HTTP_200_OK)
async def record_verdict(
    case_id: str,
    body: Verdict,
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> dict[str, Any]:
    """
    Submit the human jury's verdict to resume the Arbitrator graph.

    Phase 19: Protected by SIWE + JWT — requires steward role (Safe operator).
    """
    c = _cases.get(case_id)
    if not c:
        raise HTTPException(status_code=404, detail="Case not found.")
    if c.get("verdict"):
        raise HTTPException(status_code=409, detail="Verdict already recorded.")

    thread_id = c["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    resume_state = {
        "verdict": body.model_dump(),
        "requires_human_token": False,
    }

    try:
        final = arbitrator_graph.invoke(resume_state, config=config)
    except Exception as exc:
        logger.exception("Arbitrator resume error for case %s", case_id)
        raise HTTPException(status_code=500, detail=str(exc))

    c["verdict"] = body.model_dump()
    c["remedy_executed"] = final.get("remedy_executed", False)
    c["status"] = "remedy_executed" if c["remedy_executed"] else "verdict_rendered"

    return {
        "case_id": case_id,
        "status": c["status"],
        "outcome": body.outcome,
        "remedy_executed": c["remedy_executed"],
    }


# ── GET /arbitration/disputes/{id}/jury ───────────────────────────────────────

@router.get("/disputes/{case_id}/jury", status_code=status.HTTP_200_OK)
async def get_jury(case_id: str) -> dict[str, Any]:
    c = _cases.get(case_id)
    if not c:
        raise HTTPException(status_code=404, detail="Case not found.")
    return {"case_id": case_id, "jury": c.get("jury_selected", [])}
