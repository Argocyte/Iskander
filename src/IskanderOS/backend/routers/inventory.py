"""
Inventory router — exposes the Web3 Inventory Agent via HTTP.

GET /inventory/report — runs the LangGraph inventory graph and returns
the Valueflows REA report. Read-only; no EVM state changes.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, status

from backend.agents.inventory_agent import inventory_graph

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get(
    "/report",
    summary="Run the Web3 Inventory Agent and return a Valueflows REA report",
)
async def get_inventory_report() -> dict:
    """
    Invokes the inventory agent graph synchronously.
    Returns a Valueflows REA-formatted treasury inventory.
    """
    try:
        result = inventory_graph.invoke({
            "messages":   [],
            "agent_id":   "inventory-agent-v1",
            "action_log": [],
            "error":      None,
            "resources":  [],
            "rea_report": None,
        })
        return result.get("rea_report") or {}
    except Exception as exc:
        logger.error("inventory_agent_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
