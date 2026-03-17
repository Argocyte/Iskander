"""
/treasury — Payment validation, Mondragon ratio enforcement, HITL tx approval.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.agents.library.treasurer import treasury_graph
from backend.auth.dependencies import AuthenticatedUser, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/treasury", tags=["treasury"])


# ── Request / Response schemas ────────────────────────────────────────────────


class PaymentRequest(BaseModel):
    """Incoming payment request from the frontend or another agent."""
    type: str = Field("internal_payroll", description="internal_payroll | internal_reimbursement | external_vendor | treasury_transfer")
    to: str = Field(..., description="Recipient Ethereum address.")
    amount: float = Field(..., ge=0, description="Payment amount in token units.")
    value_wei: int = Field(0, description="Payment amount in wei (for Safe tx).")
    lowest_member_pay: float = Field(1.0, ge=0, description="Lowest-paid member's last compensation (for ratio check).")
    ratio_cap: float = Field(6.0, ge=1, description="Cooperative's Mondragon ratio cap.")
    nonce: int | None = None
    data: str = "0x"
    note: str = ""


class PaymentResponse(BaseModel):
    thread_id: str
    status: str
    safe_tx_draft: dict[str, Any] | None = None
    mondragon_check: dict[str, Any] | None = None
    action_log: list[dict[str, Any]] = []
    error: str | None = None


class ApproveRequest(BaseModel):
    thread_id: str
    approved: bool
    reason: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/payment", response_model=PaymentResponse)
async def submit_payment(
    req: PaymentRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
):
    """Submit a payment request.  Runs to HITL breakpoint for human approval."""
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [],
        "agent_id": "treasurer-agent-v1",
        "action_log": [],
        "error": None,
        "payment_request": req.model_dump(),
        "mondragon_check": None,
        "safe_tx_draft": None,
        "hitl_approved": None,
        "requires_human_token": False,
    }

    try:
        treasury_graph.invoke(initial_state, config=config)
        snapshot = treasury_graph.get_state(config)
        state = snapshot.values
    except Exception as exc:
        logger.exception("Treasury agent failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    # Check for Mondragon violation.
    check = state.get("mondragon_check", {}) or {}
    if check.get("violation"):
        return PaymentResponse(
            thread_id=thread_id,
            status="rejected_mondragon_violation",
            mondragon_check=check,
            action_log=state.get("action_log", []),
            error=state.get("error"),
        )

    return PaymentResponse(
        thread_id=thread_id,
        status="pending_human_approval",
        safe_tx_draft=state.get("safe_tx_draft"),
        mondragon_check=check,
        action_log=state.get("action_log", []),
    )


@router.post("/approve", response_model=PaymentResponse)
async def approve_payment(
    req: ApproveRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
):
    """Cast human approval/rejection vote, resume graph."""
    config = {"configurable": {"thread_id": req.thread_id}}

    try:
        snapshot = treasury_graph.get_state(config)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Thread {req.thread_id} not found.")

    state = snapshot.values
    if state.get("hitl_approved") is not None:
        raise HTTPException(status_code=409, detail="Vote already cast.")

    treasury_graph.update_state(
        config,
        {"hitl_approved": req.approved},
        as_node="human_approve",
    )
    treasury_graph.invoke(None, config=config)

    updated = treasury_graph.get_state(config).values
    status = "approved" if req.approved else "rejected"

    return PaymentResponse(
        thread_id=req.thread_id,
        status=status,
        safe_tx_draft=updated.get("safe_tx_draft"),
        mondragon_check=updated.get("mondragon_check"),
        action_log=updated.get("action_log", []),
    )
