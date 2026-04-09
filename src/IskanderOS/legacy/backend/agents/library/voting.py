"""
VotingAgent — Deterministic stance validation and closing condition evaluation.

No LLM calls. Pure cooperative governance logic.

Graph: validate_stance -> record_stance -> compute_tally
  -> evaluate_closing_condition -> [conditional: notify_block | trigger_outcome | END]

Closing rules:
- Consent: closes on any 'block' stance (if config allows)
- Consensus: closes at deadline OR unanimous agreement
- All others: close at closing_at deadline only
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.state import VotingState
from backend.config import settings
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)
AGENT_ID = "voting-agent-v1"

# Process types where 'block' is a valid stance
BLOCK_ALLOWED = {"consent", "consensus"}


def validate_stance(state: VotingState) -> dict[str, Any]:
    """Validate stance is legal for the process type."""
    stance = state.get("stance", "")
    process_type = state.get("process_type", "")

    if stance == "block" and process_type not in BLOCK_ALLOWED:
        action = AgentAction(
            agent_id=AGENT_ID,
            action="REJECT — block not allowed",
            rationale=f"Block stance is only valid for consent/consensus, not {process_type}",
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"stance": stance, "process_type": process_type},
        )
        return {
            **state,
            "error": f"Block stance not allowed for {process_type} process",
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Validate stance: {stance}",
        rationale="Stance is valid for the process type",
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"stance": stance, "process_type": process_type},
    )
    return {
        **state,
        "error": None,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def record_stance(state: VotingState) -> dict[str, Any]:
    """Package stance data for router to persist (agent does NOT write to DB)."""
    action = AgentAction(
        agent_id=AGENT_ID,
        action="Record stance in state",
        rationale="Stance packaged for router persistence",
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"member_did": state.get("member_did"), "stance": state.get("stance")},
    )
    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def compute_tally(state: VotingState) -> dict[str, Any]:
    """Aggregate all existing stances into a tally dict."""
    stances = state.get("existing_stances", [])
    tally: dict[str, Any] = {"agree": 0, "abstain": 0, "disagree": 0, "block": 0, "total": 0}
    options: dict[str, int] = {}

    for s in stances:
        stance_val = s.get("stance", "")
        if stance_val in tally and stance_val != "total":
            tally[stance_val] += 1
        else:
            options[stance_val] = options.get(stance_val, 0) + 1
        tally["total"] += 1

    if options:
        tally["options"] = options

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Compute tally: {tally['total']} stances",
        rationale="Aggregated all stances for closing condition evaluation",
        ethical_impact=EthicalImpactLevel.LOW,
        payload=tally,
    )
    return {
        **state,
        "current_tally": tally,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def evaluate_closing_condition(state: VotingState) -> dict[str, Any]:
    """Apply process-specific closing rules."""
    tally = state.get("current_tally", {})
    process_type = state.get("process_type", "")
    closing_at = state.get("closing_at")
    quorum_pct = state.get("quorum_pct", 0)
    total = tally.get("total", 0)
    closed = False
    reason = None

    # Check quorum — conservative: if a quorum percentage is required but we
    # have no eligible_count in state, we cannot confirm quorum is met.
    quorum_met = True
    if quorum_pct > 0:
        # Without an eligible member count, we cannot verify quorum.
        # Default to not met (safe: prevents premature closure).
        quorum_met = False

    # Consent: auto-close on block
    if process_type == "consent" and tally.get("block", 0) > 0:
        if settings.deliberation_consent_auto_close_on_block:
            closed, reason = True, "block"

    # Consensus: close on unanimous or deadline
    elif process_type == "consensus":
        if total > 0 and tally.get("agree", 0) == total:
            closed, reason = True, "unanimous"

    # All types: check deadline
    if not closed and closing_at:
        try:
            deadline = datetime.fromisoformat(closing_at)
            if datetime.now(timezone.utc) >= deadline:
                closed, reason = True, "deadline"
        except (ValueError, TypeError):
            pass

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Evaluate closing: closed={closed}, reason={reason}",
        rationale=f"Process {process_type}: {tally}",
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"closed": closed, "reason": reason, "quorum_met": quorum_met},
    )
    return {
        **state,
        "closing_condition_met": closed,
        "close_reason": reason,
        "quorum_met": quorum_met,
        "requires_human_token": reason == "block",
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def notify_block(state: VotingState) -> dict[str, Any]:
    """Prepare block notification data for router to broadcast."""
    action = AgentAction(
        agent_id=AGENT_ID,
        action="Block stance notification prepared",
        rationale="Member exercised blocking objection; author must be notified",
        ethical_impact=EthicalImpactLevel.HIGH,
        payload={"blocker": state.get("member_did"), "reason": state.get("reason")},
    )
    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def trigger_outcome(state: VotingState) -> dict[str, Any]:
    """Signal router to invoke OutcomeAgent."""
    action = AgentAction(
        agent_id=AGENT_ID,
        action="Trigger OutcomeAgent",
        rationale=f"Closing condition met: {state.get('close_reason')}",
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "proposal_id": state.get("proposal_id"),
            "close_reason": state.get("close_reason"),
        },
    )
    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def _route_after_validation(state: VotingState) -> str:
    """Short-circuit to END if validation set an error."""
    if state.get("error"):
        return END
    return "record_stance"


def _route_after_evaluation(state: VotingState) -> str:
    """Route based on closing condition evaluation."""
    if state.get("close_reason") == "block":
        return "notify_block"
    if state.get("closing_condition_met"):
        return "trigger_outcome"
    return END


def build_voting_graph():
    """Compile the VotingAgent LangGraph."""
    g = StateGraph(VotingState)
    g.add_node("validate_stance", validate_stance)
    g.add_node("record_stance", record_stance)
    g.add_node("compute_tally", compute_tally)
    g.add_node("evaluate_closing_condition", evaluate_closing_condition)
    g.add_node("notify_block", notify_block)
    g.add_node("trigger_outcome", trigger_outcome)

    g.set_entry_point("validate_stance")
    # Short-circuit: if validation fails, skip downstream processing
    g.add_conditional_edges(
        "validate_stance",
        _route_after_validation,
        {"record_stance": "record_stance", END: END},
    )
    g.add_edge("record_stance", "compute_tally")
    g.add_edge("compute_tally", "evaluate_closing_condition")
    g.add_conditional_edges(
        "evaluate_closing_condition",
        _route_after_evaluation,
        {"notify_block": "notify_block", "trigger_outcome": "trigger_outcome", END: END},
    )
    g.add_edge("notify_block", END)
    g.add_edge("trigger_outcome", END)

    return g.compile(checkpointer=MemorySaver())


voting_graph = build_voting_graph()
