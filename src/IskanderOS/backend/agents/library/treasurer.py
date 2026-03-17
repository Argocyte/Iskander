"""
Finance & Treasury Agent — Mondragon pay-ratio enforcement, Safe tx drafting.

Graph: validate_payment → check_mondragon_ratio → draft_payment_tx
       → [HITL: human_approve] → END
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.core import load_prompt
from backend.agents.core.glass_box_parser import GlassBoxParser
from backend.agents.core.persona_generator import build_agent_prompt
from backend.agents.state import TreasuryState
from backend.config import settings
from backend.routers.power import agents_are_paused
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "treasurer-agent-v1"

_role_prompt = load_prompt("prompt_treasurer.txt")
_parser = GlassBoxParser()

# ── Payment type constants ────────────────────────────────────────────────────

INTERNAL_PAYROLL = "internal_payroll"
INTERNAL_REIMBURSEMENT = "internal_reimbursement"
EXTERNAL_VENDOR = "external_vendor"
TREASURY_TRANSFER = "treasury_transfer"

_EXTERNAL_TYPES = {EXTERNAL_VENDOR, TREASURY_TRANSFER}


# ── Node 1: Validate payment request ─────────────────────────────────────────


def validate_payment(state: TreasuryState) -> dict[str, Any]:
    """Parse and validate payment request against cooperative rules."""
    if agents_are_paused():
        return {
            **state,
            "error": "Agents paused (low power mode). Retry when power restored.",
        }

    req = state.get("payment_request")
    if not req:
        return {**state, "error": "No payment request provided."}

    payment_type = req.get("type", INTERNAL_PAYROLL)
    # External payments ALWAYS require human approval per cooperative bylaws.
    force_hitl = payment_type in _EXTERNAL_TYPES

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Validate {payment_type} payment request",
        rationale=(
            f"Payment type '{payment_type}' received.  "
            f"{'External payment — requires_human_token forced true.' if force_hitl else 'Internal payment — proceeding to ratio check.'}"
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={"payment_type": payment_type, "recipient": req.get("to", "unknown")},
    )

    return {
        **state,
        "requires_human_token": force_hitl or state.get("requires_human_token", False),
        "action_log": state.get("action_log", []) + [action.model_dump()],
        "error": None,
    }


# ── Node 2: Check Mondragon pay ratio ────────────────────────────────────────

# Default ratio cap if not specified in constitution (Mondragon uses ~6:1).
DEFAULT_PAY_RATIO_CAP = 6


def check_mondragon_ratio(state: TreasuryState) -> dict[str, Any]:
    """Validate that the payment does not violate the Mondragon ratio cap.

    For non-payroll payments, this node passes through without enforcement.
    """
    req = state.get("payment_request", {}) or {}
    payment_type = req.get("type", INTERNAL_PAYROLL)

    # Only enforce ratio on internal payroll.
    if payment_type != INTERNAL_PAYROLL:
        return {
            **state,
            "mondragon_check": {"skipped": True, "reason": f"Not payroll ({payment_type})."},
        }

    proposed_amount = float(req.get("amount", 0))
    lowest_pay = float(req.get("lowest_member_pay", 1))  # Provided by caller / DB.
    ratio_cap = float(req.get("ratio_cap", DEFAULT_PAY_RATIO_CAP))

    if lowest_pay <= 0:
        lowest_pay = 1  # Prevent division by zero; flag in rationale.

    computed_ratio = proposed_amount / lowest_pay
    violation = computed_ratio > ratio_cap

    check_result = {
        "proposed_amount": proposed_amount,
        "lowest_member_pay": lowest_pay,
        "computed_ratio": round(computed_ratio, 2),
        "ratio_cap": ratio_cap,
        "violation": violation,
    }

    if violation:
        action = AgentAction(
            agent_id=AGENT_ID,
            action="REFUSE payment — Mondragon ratio violation",
            rationale=(
                f"Proposed payment {proposed_amount} / lowest pay {lowest_pay} "
                f"= {computed_ratio:.2f}:1, exceeding cap of {ratio_cap}:1.  "
                f"CCIN Principle 9 (Pay Equity) violated.  Payment blocked."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload=check_result,
        )
        return {
            **state,
            "mondragon_check": check_result,
            "error": f"Mondragon ratio violation: {computed_ratio:.2f}:1 exceeds {ratio_cap}:1 cap.",
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Mondragon ratio check passed",
        rationale=(
            f"Ratio {computed_ratio:.2f}:1 is within the {ratio_cap}:1 cap.  "
            f"Payment may proceed to drafting."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload=check_result,
    )

    return {
        **state,
        "mondragon_check": check_result,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 3: Draft Safe multi-sig transaction ─────────────────────────────────


def draft_payment_tx(state: TreasuryState) -> dict[str, Any]:
    """Draft an unsigned Safe multi-sig transaction for the payment.

    Skips drafting if a Mondragon violation was detected.
    """
    # Abort if Mondragon ratio was violated.
    check = state.get("mondragon_check", {}) or {}
    if check.get("violation"):
        return {
            **state,
            "safe_tx_draft": None,
            "requires_human_token": True,
        }

    req = state.get("payment_request", {}) or {}
    safe = settings.safe_address
    to_addr = req.get("to", "0x" + "0" * 40)
    value_wei = str(req.get("value_wei", 0))
    note = req.get("note", "Payment drafted by treasurer-agent-v1")

    tx_draft = {
        "safe": safe,
        "to": to_addr,
        "value": value_wei,
        "data": req.get("data", "0x"),
        "operation": 0,
        "safeTxGas": 0,
        "baseGas": 0,
        "gasPrice": "0",
        "gasToken": "0x" + "0" * 40,
        "refundReceiver": "0x" + "0" * 40,
        "nonce": req.get("nonce"),
        "chainId": settings.evm_chain_id,
        "_iskander_note": note,
        "_iskander_payment_type": req.get("type", INTERNAL_PAYROLL),
        "_iskander_mondragon_ratio": check.get("computed_ratio"),
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Draft unsigned Safe multi-sig payment transaction",
        rationale=(
            "Transaction drafted for human M-of-N signing.  "
            "Agent does NOT have signing authority per cooperative bylaws."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload={"to": to_addr, "value_wei": value_wei},
    )

    return {
        **state,
        "safe_tx_draft": tx_draft,
        "hitl_approved": None,  # Awaiting human vote.
        "requires_human_token": True,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: HITL breakpoint ──────────────────────────────────────────────────


def human_approve(state: TreasuryState) -> dict[str, Any]:
    """No-op node — graph suspends here for human M-of-N voting.

    State mutation (hitl_approved) happens externally via the treasury
    router's /treasury/approve endpoint, same pattern as governance agent.
    """
    return state


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_treasury_graph():
    """Compile the Treasury Agent LangGraph with HITL breakpoint."""
    g = StateGraph(TreasuryState)
    g.add_node("validate_payment", validate_payment)
    g.add_node("check_mondragon_ratio", check_mondragon_ratio)
    g.add_node("draft_payment_tx", draft_payment_tx)
    g.add_node("human_approve", human_approve)
    g.set_entry_point("validate_payment")
    g.add_edge("validate_payment", "check_mondragon_ratio")
    g.add_edge("check_mondragon_ratio", "draft_payment_tx")
    g.add_edge("draft_payment_tx", "human_approve")
    g.add_edge("human_approve", END)
    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_approve"],
    )


treasury_graph = build_treasury_graph()
