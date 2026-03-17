"""
/fiat — Fiat-Crypto Bridge API (Phase 26).

Endpoints for cFIAT mint/burn proposals, reserve balance queries, and
solvency status. All mint/burn operations go through the Fiat Gateway
Agent's LangGraph with mandatory Glass Box auditing.

ANTI-EXTRACTIVE:
  This router exists so cooperatives can bypass Visa, Mastercard, and Stripe.
  Inter-cooperative commerce settles directly via cooperative bank rails.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from backend.agents.library.fiat_gateway import AGENT_ID, fiat_gateway_graph
from backend.api.hitl_rate_limiter import HITLRateLimiter
from backend.auth.dependencies import AuthenticatedUser, require_role
from backend.finance.open_banking_client import OpenBankingClient
from backend.finance.solvency_oracle import SolvencyOracle
from backend.schemas.fiat import (
    BurnRequest,
    FiatOperationResponse,
    MintRequest,
    ReserveResponse,
    SolvencyResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fiat", tags=["fiat"])


# ── Mint ──────────────────────────────────────────────────────────────────────


@router.post("/mint", response_model=FiatOperationResponse)
async def mint(
    req: MintRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
):
    """Trigger a cFIAT mint proposal via the Fiat Gateway Agent.

    The agent checks the cooperative bank reserve, evaluates solvency,
    and proposes the mint. If the amount exceeds the approval threshold,
    the graph pauses at the HITL gate for steward approval.
    """
    await HITLRateLimiter.get_instance().check(user.address, "/fiat/mint")
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [],
        "agent_id": AGENT_ID,
        "action_log": [],
        "error": None,
        "reserve_balance": None,
        "on_chain_supply": None,
        "solvency_ratio": None,
        "proposed_action": "mint",
        "proposed_amount": req.amount,
        "chain_tx_result": None,
        "requires_human_token": False,
    }

    try:
        fiat_gateway_graph.invoke(initial_state, config=config)
        snapshot = fiat_gateway_graph.get_state(config)
        state = snapshot.values
    except Exception as exc:
        logger.exception("Fiat Gateway mint failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if state.get("error"):
        raise HTTPException(status_code=422, detail=state["error"])

    # Determine status.
    if state.get("requires_human_token"):
        status = "pending_approval"
    elif state.get("chain_tx_result", {}).get("status") == "drafted":
        status = "executed"
    else:
        status = "proposed"

    tx_result = state.get("chain_tx_result") or {}

    return FiatOperationResponse(
        thread_id=thread_id,
        status=status,
        operation_type="mint",
        amount=req.amount,
        solvency_ratio=state.get("solvency_ratio"),
        tx_hash=tx_result.get("tx_hash"),
        message=(
            f"Mint proposal for {req.amount} wei. "
            f"Solvency ratio: {state.get('solvency_ratio', 'N/A')}. "
            f"Status: {status}. Rationale: {req.rationale}"
        ),
    )


# ── Burn ──────────────────────────────────────────────────────────────────────


@router.post("/burn", response_model=FiatOperationResponse)
async def burn(
    req: BurnRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
):
    """Trigger a cFIAT burn proposal via the Fiat Gateway Agent.

    Burns reduce cFIAT supply and may trigger an off-ramp transfer to the
    cooperative's physical bank account.
    """
    await HITLRateLimiter.get_instance().check(user.address, "/fiat/burn")
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [],
        "agent_id": AGENT_ID,
        "action_log": [],
        "error": None,
        "reserve_balance": None,
        "on_chain_supply": None,
        "solvency_ratio": None,
        "proposed_action": "burn",
        "proposed_amount": req.amount,
        "chain_tx_result": None,
        "requires_human_token": False,
    }

    try:
        fiat_gateway_graph.invoke(initial_state, config=config)
        snapshot = fiat_gateway_graph.get_state(config)
        state = snapshot.values
    except Exception as exc:
        logger.exception("Fiat Gateway burn failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if state.get("error"):
        raise HTTPException(status_code=422, detail=state["error"])

    if state.get("requires_human_token"):
        status = "pending_approval"
    elif state.get("chain_tx_result", {}).get("status") == "drafted":
        status = "executed"
    else:
        status = "proposed"

    tx_result = state.get("chain_tx_result") or {}

    return FiatOperationResponse(
        thread_id=thread_id,
        status=status,
        operation_type="burn",
        amount=req.amount,
        solvency_ratio=state.get("solvency_ratio"),
        tx_hash=tx_result.get("tx_hash"),
        message=(
            f"Burn proposal for {req.amount} wei. "
            f"Solvency ratio: {state.get('solvency_ratio', 'N/A')}. "
            f"Status: {status}. Rationale: {req.rationale}"
        ),
    )


# ── Reserve Balance ───────────────────────────────────────────────────────────


@router.get("/reserve", response_model=ReserveResponse)
async def get_reserve(
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """Query the current cooperative bank reserve balance.

    Calls OpenBankingClient.get_fiat_reserve_balance() and returns the
    current fiat balance backing the cFIAT token supply.
    """
    client = OpenBankingClient.get_instance()

    try:
        balance, _action = await client.get_fiat_reserve_balance()
    except Exception as exc:
        logger.exception("Reserve query failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Bank API error: {exc}")

    return ReserveResponse(
        balance=str(balance.balance),
        currency=balance.currency,
        account_id=balance.account_id,
        institution=balance.institution,
        as_of=balance.as_of.isoformat(),
    )


# ── Solvency Status ──────────────────────────────────────────────────────────


@router.get("/solvency", response_model=SolvencyResponse)
async def get_solvency(
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """Query the current solvency status of the cFIAT system.

    Calls SolvencyOracle.check_solvency() to compare bank reserve
    against on-chain cFIAT supply and escrow totals.
    """
    oracle = SolvencyOracle.get_instance()

    try:
        snapshot, _action = await oracle.check_solvency()
    except Exception as exc:
        logger.exception("Solvency check failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Solvency oracle error: {exc}")

    return SolvencyResponse(
        fiat_reserve=str(snapshot.fiat_reserve),
        total_escrow_wei=snapshot.total_escrow_wei,
        cfiat_supply_wei=snapshot.cfiat_supply_wei,
        solvency_ratio=snapshot.solvency_ratio,
        circuit_breaker_active=snapshot.circuit_breaker_active,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )
