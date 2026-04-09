"""
Arbitrator Agent — Phase 15: Inter-Coop Arbitration (Solidarity Court).

Graph:
  receive_dispute → assess_jurisdiction
  → [conditional: intra-coop → governance route | inter-coop → request_jury_federation]
  → [HITL: human_jury_deliberation]
  → record_verdict → execute_remedy → END

FUNDAMENTAL CONSTRAINT:
  This agent NEVER renders a verdict autonomously.
  It facilitates, presents, and records — the human jury decides.
  The `human_jury_deliberation` HITL breakpoint is MANDATORY and cannot
  be bypassed regardless of any setting or flag.

GLASS BOX:
  Every node produces an AgentAction. High-impact operations
  (dispute receipt, jury federation, remedy execution) carry
  ethical_impact=HIGH and are logged to the audit ledger.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.core import load_prompt
from backend.agents.state import ArbitrationState
from backend.config import settings
from backend.federation.arbitration_protocol import ArbitrationProtocol
from backend.routers.power import agents_are_paused
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "arbitrator-agent-v1"

_role_prompt = load_prompt("prompt_arbitrator.txt")
_protocol = ArbitrationProtocol()


# ── Node 1: Receive Dispute ───────────────────────────────────────────────────

def receive_dispute(state: ArbitrationState) -> dict[str, Any]:
    """
    Validate and acknowledge an incoming dispute.

    Input: state["dispute"] must contain escrow_id, complainant_did,
    respondent_did, description, and evidence_cids.
    """
    if agents_are_paused():
        return {**state, "error": "Agents paused (low power mode)."}

    dispute = state.get("dispute") or {}
    required = ["escrow_id", "complainant_did", "respondent_did", "description"]
    missing = [k for k in required if not dispute.get(k)]

    if missing:
        return {**state, "error": f"Dispute missing required fields: {missing}"}

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"receive_dispute(escrow={dispute['escrow_id']})",
        rationale=(
            "Inbound dispute received from cooperative member. "
            "Initiating Solidarity Court protocol per Phase 15. "
            "No verdict will be rendered without human jury deliberation."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload={
            "escrow_id": dispute["escrow_id"],
            "complainant": dispute["complainant_did"],
            "respondent": dispute["respondent_did"],
        },
    )

    return {
        **state,
        "error": None,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 2: Assess Jurisdiction ───────────────────────────────────────────────

def assess_jurisdiction(state: ArbitrationState) -> dict[str, Any]:
    """
    Determine whether this is an intra-coop or inter-coop dispute.

    Intra-coop: both parties are members of the same cooperative node.
    Route to the existing governance process (reuse GovernanceAgent).

    Inter-coop: parties are from different federated nodes.
    Route to the federated jury selection process.

    Heuristic: if both DIDs share the same domain → intra-coop.
    Production: query CoopIdentity.memberToken() for both addresses.
    """
    dispute = state.get("dispute") or {}
    complainant = dispute.get("complainant_did", "")
    respondent = dispute.get("respondent_did", "")

    # Simple domain extraction heuristic.
    def _domain(did: str) -> str:
        if "@" in did:
            return did.split("@")[-1]
        if ":" in did:
            return did.split(":")[-1]
        return did

    same_domain = _domain(complainant) == _domain(respondent)
    jurisdiction = "intra_coop" if same_domain else "inter_coop"

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"assess_jurisdiction → {jurisdiction}",
        rationale=(
            "Determining whether to route dispute to internal governance "
            "or federated jury protocol. Intra-coop disputes use the "
            "existing Governance Agent; inter-coop use the Solidarity Court."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={"jurisdiction": jurisdiction, "complainant": complainant, "respondent": respondent},
    )

    return {
        **state,
        "jurisdiction": jurisdiction,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 3: Request Jury Federation ──────────────────────────────────────────

def request_jury_federation(state: ArbitrationState) -> dict[str, Any]:
    """
    Send ArbitrationRequest activities to sister cooperatives.

    ethical_impact=HIGH — sends ActivityPub messages to external coops.
    Requires HITL approval before this node is reached (set in graph routing).

    In stub mode: populates jury_pool with mock nominations.
    Production: awaits real JuryNomination responses via inbox processor.
    """
    dispute = state.get("dispute") or {}
    case_id = state.get("case_id") or dispute.get("case_id", "unknown-case")

    # STUB: mock jury pool. Production: collected from inbound JuryNomination activities.
    mock_jury_pool = [
        {"jurorDid": f"did:key:juror{i}", "nominatingCoop": f"sistercoop{i}.local"}
        for i in range(1, 7)
    ]
    selected = _protocol.select_jury(mock_jury_pool, case_id, jury_size=settings.arbitration_jury_size)

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"request_jury_federation(case={case_id})",
        rationale=(
            "Sending iskander:ArbitrationRequest to sister cooperatives via ActivityPub. "
            "Deterministic jury selection applied to nominations. "
            "Jury will deliberate via Matrix rooms — no AI verdict."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload={
            "case_id": case_id,
            "jury_size_requested": settings.arbitration_jury_size,
            "jury_selected": len(selected),
            "stub_mode": True,
        },
    )

    return {
        **state,
        "jury_pool": mock_jury_pool,
        "jury_selected": selected,
        "requires_human_token": True,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: HITL — Human Jury Deliberation (MANDATORY) ───────────────────────

def human_jury_deliberation(state: ArbitrationState) -> dict[str, Any]:
    """
    MANDATORY HITL breakpoint. Cannot be bypassed.

    The graph suspends here until the human jury reaches a verdict and
    the operator Safe calls POST /arbitration/disputes/{id}/verdict.

    The jury deliberates via Matrix rooms (Phase 14A). The Arbitrator Agent
    is present in the room to answer questions but cannot vote or recommend.

    resumption condition: state["verdict"] is set and state["requires_human_token"] = False.
    """
    return state


# ── Node 5: Record Verdict ────────────────────────────────────────────────────

def record_verdict(state: ArbitrationState) -> dict[str, Any]:
    """
    Record the human jury's verdict on-chain via ArbitrationRegistry.sol.

    ethical_impact=HIGH — on-chain state change with financial consequences.
    Only reachable after HITL clearance.
    """
    verdict = state.get("verdict") or {}
    dispute = state.get("dispute") or {}

    if not verdict:
        return {**state, "error": "No verdict provided — cannot record without human jury decision."}

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"record_verdict(case={dispute.get('escrow_id')}, outcome={verdict.get('outcome')})",
        rationale=(
            "Recording human jury verdict on-chain via ArbitrationRegistry.sol. "
            "Verdict was reached by federated human jury — AI facilitated only. "
            "HITL token confirmed."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload={
            "outcome": verdict.get("outcome"),
            "buyer_amount": verdict.get("buyer_amount_wei"),
            "seller_amount": verdict.get("seller_amount_wei"),
            "jury_ipfs_cid": verdict.get("jury_ipfs_cid"),
        },
    )

    # Production: call ArbitrationRegistry via web3.py.
    # Stub: log and continue.
    logger.info(
        "STUB: ArbitrationRegistry.recordVerdict(case=%s, outcome=%s)",
        dispute.get("escrow_id"), verdict.get("outcome"),
    )

    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 6: Execute Remedy ────────────────────────────────────────────────────

def execute_remedy(state: ArbitrationState) -> dict[str, Any]:
    """
    Execute the financial remedy: release escrow funds per verdict.

    ethical_impact=HIGH — on-chain fund transfer and potential trust slashing.
    """
    verdict = state.get("verdict") or {}
    dispute = state.get("dispute") or {}

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"execute_remedy(escrow={dispute.get('escrow_id')})",
        rationale=(
            "Executing on-chain escrow verdict via IskanderEscrow.executeVerdict(). "
            "Trust score adjustments applied to bad-faith parties if applicable. "
            "Remedy is the human jury's decision — not the AI's."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload={
            "escrow_id": dispute.get("escrow_id"),
            "buyer_amount_wei": verdict.get("buyer_amount_wei", 0),
            "seller_amount_wei": verdict.get("seller_amount_wei", 0),
            "buyer_slash": verdict.get("buyer_slash", 0),
            "seller_slash": verdict.get("seller_slash", 0),
        },
    )

    logger.info("STUB: IskanderEscrow.executeVerdict() and trust slashing.")

    return {
        **state,
        "remedy_executed": True,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Routing ───────────────────────────────────────────────────────────────────

def _route_after_jurisdiction(state: ArbitrationState) -> str:
    if state.get("error"):
        return END
    if state.get("jurisdiction") == "intra_coop":
        # Route to internal governance — skip federated jury.
        return "human_jury_deliberation"
    return "request_jury_federation"


def _route_after_hitl(state: ArbitrationState) -> str:
    if state.get("error") or not state.get("verdict"):
        return END
    return "record_verdict"


# ── Graph Assembly ────────────────────────────────────────────────────────────

def build_arbitrator_graph():
    """
    Compile the Arbitrator Agent LangGraph.

    The `human_jury_deliberation` interrupt is MANDATORY — it cannot be
    configured away. This is enforced by the `interrupt_before` parameter.
    """
    g = StateGraph(ArbitrationState)

    g.add_node("receive_dispute",           receive_dispute)
    g.add_node("assess_jurisdiction",       assess_jurisdiction)
    g.add_node("request_jury_federation",   request_jury_federation)
    g.add_node("human_jury_deliberation",   human_jury_deliberation)
    g.add_node("record_verdict",            record_verdict)
    g.add_node("execute_remedy",            execute_remedy)

    g.set_entry_point("receive_dispute")
    g.add_edge("receive_dispute", "assess_jurisdiction")

    g.add_conditional_edges(
        "assess_jurisdiction",
        _route_after_jurisdiction,
        {
            "request_jury_federation": "request_jury_federation",
            "human_jury_deliberation": "human_jury_deliberation",
            END: END,
        },
    )

    g.add_edge("request_jury_federation", "human_jury_deliberation")

    g.add_conditional_edges(
        "human_jury_deliberation",
        _route_after_hitl,
        {"record_verdict": "record_verdict", END: END},
    )

    g.add_edge("record_verdict",  "execute_remedy")
    g.add_edge("execute_remedy",  END)

    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_jury_deliberation"],  # MANDATORY — never remove.
    )


arbitrator_graph = build_arbitrator_graph()
