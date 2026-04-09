"""
escrow.py — Phase 15: Inter-Coop Escrow API Router.

Endpoints:
  POST /escrow/create         — Create a new inter-coop escrow (via Safe).
  GET  /escrow/{id}           — Get escrow status.
  POST /escrow/{id}/release   — Confirm delivery and release funds (buyer only).
  POST /escrow/{id}/dispute   — Raise a dispute (triggers arbitration flow).

All on-chain calls are stubbed. Production: call IskanderEscrow.sol via web3.py
with the buyer's Safe as the transaction sender.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import AuthenticatedUser, get_current_user
from backend.schemas.arbitration import EscrowCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/escrow", tags=["escrow"])

# STUB: in-memory escrow registry.
_escrows: dict[str, dict[str, Any]] = {}
_escrow_counter = 0


def _next_escrow_id() -> str:
    global _escrow_counter
    _escrow_counter += 1
    return str(_escrow_counter)


# ── POST /escrow/create ───────────────────────────────────────────────────────

@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_escrow(
    body: EscrowCreate,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Create a new escrow. Stub: records off-chain and returns mock escrow_id.
    Production: submit ERC-20 approve + IskanderEscrow.createEscrow() via Safe.
    """
    buyer_address = user.address
    escrow_id = _next_escrow_id()
    _escrows[escrow_id] = {
        "escrow_id": escrow_id,
        "buyer_coop": buyer_address,
        "seller_coop": body.seller_coop_address,
        "token_address": body.token_address,
        "amount_wei": body.amount_wei,
        "terms_ipfs_cid": body.terms_ipfs_cid,
        "expires_at": body.expires_at,
        "status": "Active",
        "has_active_case": False,
    }
    logger.info("STUB: Escrow %s created (buyer=%s, seller=%s)", escrow_id, buyer_address, body.seller_coop_address)
    return {"escrow_id": escrow_id, "status": "Active", "stub": True}


# ── GET /escrow/{id} ──────────────────────────────────────────────────────────

@router.get("/{escrow_id}", status_code=status.HTTP_200_OK)
async def get_escrow(escrow_id: str) -> dict[str, Any]:
    e = _escrows.get(escrow_id)
    if not e:
        raise HTTPException(status_code=404, detail="Escrow not found.")
    return e


# ── POST /escrow/{id}/release ─────────────────────────────────────────────────

@router.post("/{escrow_id}/release", status_code=status.HTTP_200_OK)
async def release_escrow(
    escrow_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Confirm delivery and release funds to seller.
    Production: call IskanderEscrow.confirmDelivery() via buyer's Safe.
    """
    e = _escrows.get(escrow_id)
    if not e:
        raise HTTPException(status_code=404, detail="Escrow not found.")
    buyer_address = user.address
    if e["buyer_coop"] != buyer_address:
        raise HTTPException(status_code=403, detail="Only the buyer may confirm delivery.")
    if e["status"] != "Active":
        raise HTTPException(status_code=409, detail=f"Escrow status is '{e['status']}'.")

    e["status"] = "Released"
    logger.info("STUB: Escrow %s released by buyer %s", escrow_id, buyer_address)

    # Phase 18: Trigger post-trade IPD audit — record outcome in reputation graph.
    try:
        from backend.routers.ipd_audit import record_outcome_internal
        await record_outcome_internal(
            escrow_id=escrow_id,
            buyer_did=e["buyer_coop"],
            seller_did=e["seller_coop"],
            escrow_outcome="Released",
        )
    except Exception as exc:
        # Non-blocking: audit failure must not block escrow release.
        logger.warning("Phase 18: Post-trade audit failed for escrow %s: %s", escrow_id, exc)

    return {"escrow_id": escrow_id, "status": "Released"}


# ── POST /escrow/{id}/dispute ─────────────────────────────────────────────────

@router.post("/{escrow_id}/dispute", status_code=status.HTTP_202_ACCEPTED)
async def dispute_escrow(
    escrow_id: str,
    description: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Raise a dispute. Triggers the Arbitrator Agent flow via /arbitration/disputes.
    Production: call IskanderEscrow.dispute() on-chain first, then file off-chain.
    """
    complainant_address = user.address
    e = _escrows.get(escrow_id)
    if not e:
        raise HTTPException(status_code=404, detail="Escrow not found.")
    if e["status"] != "Active":
        raise HTTPException(status_code=409, detail=f"Escrow status is '{e['status']}'.")

    e["status"] = "Disputed"
    e["has_active_case"] = True

    logger.info("STUB: Escrow %s disputed by %s", escrow_id, complainant_address)

    return {
        "escrow_id": escrow_id,
        "status": "Disputed",
        "message": (
            f"Dispute recorded. File a full arbitration case at "
            f"POST /arbitration/disputes with escrow_id={escrow_id}."
        ),
    }
