"""
Stewardship Scorer Agent — Phase 23: Dynamic Impact Score Computation.

Computes Impact Scores for all cooperative members based on contribution
history (DisCO Contributory Accounting, Phase 9) and ethical audit signals
(IPD Auditor cooperation_ratio, Phase 18). Determines steward eligibility
for the liquid delegation layer and proposes threshold updates.

Graph:
  aggregate_contributions → fetch_ethical_audit → compute_impact_scores
    → evaluate_steward_eligibility → propose_threshold_update
    → [conditional: HITL or push_scores_to_chain]
    → push_scores_to_chain → END

DESIGN CONSTRAINTS:
  - Anti-hierarchical: steward roles expire when scores drop below threshold.
  - Anticipatory: warn members before their delegation status expires.
  - Glass Box Protocol: every computation step discloses formula and inputs.
  - No autonomous chain writes: score pushes are drafted, not executed,
    pending human-in-the-loop approval for threshold changes.
"""
from __future__ import annotations

import logging
import statistics
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.core import load_prompt
from backend.agents.state import StewardshipCouncilState
from backend.config import settings
from backend.routers.power import agents_are_paused
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "stewardship-scorer-v1"

_role_prompt = load_prompt("prompt_stewardship_scorer.txt")


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH NODES
# ═══════════════════════════════════════════════════════════════════════════════


# ── Node 1: Aggregate contributions ──────────────────────────────────────────


def aggregate_contributions(state: StewardshipCouncilState) -> dict[str, Any]:
    """Query the contributions table and compute per-node historical value.

    STUB: In production, these are asyncpg queries against the contributions
    and reputation_scores tables. Currently returns placeholder data to
    enable graph compilation and API wiring.
    """
    if agents_are_paused():
        return {**state, "error": "Agents paused (low power mode)."}

    target_nodes = state.get("target_nodes", [])

    # STUB: Replace with asyncpg queries.
    # SELECT member_did,
    #        COALESCE(SUM(care_score), 0) + COALESCE(SUM(value_tokens), 0) AS total_value
    # FROM contributions
    # GROUP BY member_did
    # [WHERE member_did = ANY($1)]  -- if target_nodes is non-empty
    contribution_aggregates: list[dict[str, Any]] = []

    # In stub mode, create placeholder data for any target nodes.
    for did in target_nodes:
        contribution_aggregates.append({
            "node_did": did,
            "total_value": 0.0,
        })

    # STUB: SELECT SUM(care_score) + SUM(value_tokens) FROM contributions
    ecosystem_total_value = sum(
        c.get("total_value", 0.0) for c in contribution_aggregates
    ) or 1.0  # Avoid division by zero.

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Aggregated contribution history",
        rationale=(
            f"Queried contributions table for {len(target_nodes) or 'all'} nodes. "
            f"Ecosystem total value: {ecosystem_total_value:.4f}. "
            "STUB: using placeholder values pending asyncpg integration."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={
            "target_count": len(target_nodes),
            "aggregates_count": len(contribution_aggregates),
            "ecosystem_total_value": ecosystem_total_value,
        },
    )

    return {
        **state,
        "contribution_aggregates": contribution_aggregates,
        "ecosystem_total_value": ecosystem_total_value,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 2: Fetch ethical audit scores ───────────────────────────────────────


def fetch_ethical_audit(state: StewardshipCouncilState) -> dict[str, Any]:
    """Query reputation_scores.cooperation_ratio for each target node.

    Reuses the IPD Auditor's cooperation data (Phase 18) as the
    Ethical_Audit_Score component of the Impact Score formula.

    STUB: In production, queries reputation_scores table via asyncpg.
    """
    if state.get("error"):
        return state

    aggregates = state.get("contribution_aggregates", [])

    # STUB: Replace with asyncpg queries.
    # SELECT node_did, cooperation_ratio FROM reputation_scores
    # WHERE node_did = ANY($1)
    ethical_audit_results: list[dict[str, Any]] = []

    for agg in aggregates:
        did = agg.get("node_did", "")
        # STUB: default to IPD prior cooperation probability for unknown nodes.
        ethical_audit_results.append({
            "node_did": did,
            "cooperation_ratio": settings.ipd_prior_cooperation,
        })

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Fetched ethical audit scores",
        rationale=(
            f"Retrieved cooperation_ratio for {len(ethical_audit_results)} nodes "
            "from reputation_scores (IPD Auditor Phase 18 data). "
            "Cooperation ratio serves as the Ethical_Audit_Score component. "
            "STUB: using IPD prior cooperation for all nodes."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={
            "nodes_queried": len(ethical_audit_results),
            "source": "reputation_scores.cooperation_ratio",
        },
    )

    return {
        **state,
        "ethical_audit_results": ethical_audit_results,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 3: Compute Impact Scores ───────────────────────────────────────────


def compute_impact_scores(state: StewardshipCouncilState) -> dict[str, Any]:
    """Apply the Impact Score formula:

    Impact_Score = (Historical_Contribution_Value / Ecosystem_Total_Value)
                   * Ethical_Audit_Score

    Clamped to [0.0, 1.0].
    """
    if state.get("error"):
        return state

    aggregates = state.get("contribution_aggregates", [])
    ethical_results = state.get("ethical_audit_results", [])
    ecosystem_total = state.get("ecosystem_total_value", 1.0)

    # Build lookup: node_did -> cooperation_ratio
    ethical_lookup: dict[str, float] = {
        e["node_did"]: e.get("cooperation_ratio", 0.0)
        for e in ethical_results
    }

    impact_scores: list[dict[str, Any]] = []
    for agg in aggregates:
        did = agg.get("node_did", "")
        contribution_value = agg.get("total_value", 0.0)
        ethical_score = ethical_lookup.get(did, 0.0)

        # Impact_Score formula from spec.
        if ecosystem_total > 0:
            raw_score = (contribution_value / ecosystem_total) * ethical_score
        else:
            raw_score = 0.0

        # Clamp to [0.0, 1.0].
        impact_score = max(0.0, min(1.0, raw_score))

        impact_scores.append({
            "node_did": did,
            "historical_contribution_value": contribution_value,
            "ethical_audit_score": ethical_score,
            "impact_score": impact_score,
        })

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Computed Impact Scores",
        rationale=(
            f"Applied formula: Impact_Score = (Contribution / {ecosystem_total:.4f}) "
            f"* Ethical_Audit_Score for {len(impact_scores)} nodes. "
            "All scores clamped to [0.0, 1.0]."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "formula": "Impact_Score = (Historical_Contribution_Value / Ecosystem_Total_Value) * Ethical_Audit_Score",
            "ecosystem_total_value": ecosystem_total,
            "scores_computed": len(impact_scores),
            "score_range": {
                "min": min((s["impact_score"] for s in impact_scores), default=0.0),
                "max": max((s["impact_score"] for s in impact_scores), default=0.0),
            },
        },
    )

    return {
        **state,
        "impact_scores": impact_scores,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: Evaluate steward eligibility ─────────────────────────────────────


def evaluate_steward_eligibility(state: StewardshipCouncilState) -> dict[str, Any]:
    """Compare each node's Impact Score against the current threshold.

    Generates anticipatory warnings for nodes within the warning margin
    of the threshold (spec: "warn nodes when delegation status is about
    to expire due to dropping contribution scores").
    """
    if state.get("error"):
        return state

    impact_scores = state.get("impact_scores", [])
    threshold = state.get("current_threshold") or settings.steward_threshold_default
    warning_margin = settings.steward_warning_margin

    anticipatory_warnings: list[dict[str, Any]] = []
    updated_scores: list[dict[str, Any]] = []

    for score_entry in impact_scores:
        score = score_entry["impact_score"]
        is_eligible = score >= threshold
        warning = None

        # Anticipatory warning: within margin of threshold.
        if is_eligible and score < (threshold + warning_margin):
            warning = (
                f"Your Impact Score ({score:.4f}) is within {warning_margin:.0%} of "
                f"the steward threshold ({threshold:.4f}). Increase contributions to "
                f"maintain steward eligibility."
            )
            anticipatory_warnings.append({
                "node_did": score_entry["node_did"],
                "impact_score": score,
                "threshold": threshold,
                "gap": score - threshold,
                "warning": warning,
            })

        updated_scores.append({
            **score_entry,
            "is_eligible_steward": is_eligible,
            "warning_message": warning,
        })

    eligible_count = sum(1 for s in updated_scores if s["is_eligible_steward"])

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Evaluated steward eligibility",
        rationale=(
            f"Compared {len(updated_scores)} Impact Scores against threshold "
            f"{threshold:.4f}. Eligible: {eligible_count}. "
            f"Warnings issued: {len(anticipatory_warnings)} (nodes within "
            f"{warning_margin:.0%} of threshold)."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "threshold": threshold,
            "total_nodes": len(updated_scores),
            "eligible_count": eligible_count,
            "warnings_count": len(anticipatory_warnings),
        },
    )

    return {
        **state,
        "impact_scores": updated_scores,
        "current_threshold": threshold,
        "anticipatory_warnings": anticipatory_warnings,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 5: Propose threshold update ────────────────────────────────────────


def propose_threshold_update(state: StewardshipCouncilState) -> dict[str, Any]:
    """Propose a new steward threshold based on score distribution.

    Proposed threshold = median(all_scores) * 0.75, ensuring a majority of
    active contributors can participate while maintaining a meaningful bar.

    If the proposed threshold differs from current by more than 5%, flag for
    HITL review before applying.
    """
    if state.get("error"):
        return state

    impact_scores = state.get("impact_scores", [])
    current_threshold = state.get("current_threshold") or settings.steward_threshold_default

    all_scores = [s["impact_score"] for s in impact_scores]

    if not all_scores:
        return {
            **state,
            "proposed_threshold": current_threshold,
            "threshold_rationale": "No scores to compute — threshold unchanged.",
            "requires_human_token": False,
            "action_log": state.get("action_log", []) + [AgentAction(
                agent_id=AGENT_ID,
                action="Threshold unchanged — no scores",
                rationale="No Impact Scores available; keeping current threshold.",
                ethical_impact=EthicalImpactLevel.LOW,
            ).model_dump()],
        }

    median_score = statistics.median(all_scores)
    proposed = round(median_score * 0.75, 4)

    # Determine if change is significant (>5% relative change).
    if current_threshold > 0:
        relative_change = abs(proposed - current_threshold) / current_threshold
    else:
        relative_change = 1.0 if proposed > 0 else 0.0

    needs_hitl = relative_change > 0.05
    rationale = (
        f"Proposed threshold: {proposed:.4f} (median={median_score:.4f} * 0.75). "
        f"Current: {current_threshold:.4f}. "
        f"Relative change: {relative_change:.2%}. "
        f"{'HITL required — change exceeds 5%.' if needs_hitl else 'Within 5% — auto-applying.'}"
    )

    ethical_impact = EthicalImpactLevel.HIGH if needs_hitl else EthicalImpactLevel.MEDIUM

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Proposed threshold update",
        rationale=rationale,
        ethical_impact=ethical_impact,
        payload={
            "current_threshold": current_threshold,
            "proposed_threshold": proposed,
            "median_score": median_score,
            "relative_change": relative_change,
            "requires_hitl": needs_hitl,
        },
    )

    return {
        **state,
        "proposed_threshold": proposed,
        "threshold_rationale": rationale,
        "requires_human_token": needs_hitl,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 6: Human review (HITL breakpoint) ──────────────────────────────────


def human_review_threshold(state: StewardshipCouncilState) -> dict[str, Any]:
    """HITL no-op node. The graph pauses here via interrupt_before when
    requires_human_token is True. The router resumes after steward approval.
    """
    return {**state, "requires_human_token": False}


# ── Node 7: Push scores to chain ────────────────────────────────────────────


def push_scores_to_chain(state: StewardshipCouncilState) -> dict[str, Any]:
    """Build the Web3 transaction to call StewardshipLedger.updateImpactScores().

    Converts float scores [0.0, 1.0] to basis points [0, 10000] for on-chain
    storage. Drafts the transaction — does NOT execute it autonomously.

    STUB: In production, uses web3.py to build and sign the transaction via
    the oracle private key.
    """
    if state.get("error"):
        return state

    impact_scores = state.get("impact_scores", [])

    # Convert to basis points for on-chain storage.
    addresses: list[str] = []
    scores_bps: list[int] = []
    for entry in impact_scores:
        # STUB: In production, resolve DID → Ethereum address via
        # credit_accounts.linked_address or CoopIdentity reverse lookup.
        address = entry.get("node_address", "0x" + "0" * 40)
        addresses.append(address)
        scores_bps.append(int(entry["impact_score"] * 10000))

    # STUB: Build unsigned transaction.
    # In production:
    #   w3 = Web3(Web3.HTTPProvider(settings.evm_rpc_url))
    #   contract = w3.eth.contract(
    #       address=settings.stewardship_ledger_address,
    #       abi=STEWARDSHIP_LEDGER_ABI,
    #   )
    #   tx = contract.functions.updateImpactScores(addresses, scores_bps).build_transaction({...})
    chain_update_result = {
        "status": "drafted",
        "contract": settings.stewardship_ledger_address,
        "function": "updateImpactScores",
        "addresses_count": len(addresses),
        "scores_bps_sample": scores_bps[:5],
        "note": "STUB — transaction not submitted. Pending oracle integration.",
    }

    # Apply proposed threshold if it was approved.
    proposed = state.get("proposed_threshold")
    current = state.get("current_threshold")
    threshold_applied = proposed if proposed is not None else current

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Drafted on-chain score update",
        rationale=(
            f"Prepared updateImpactScores() call for {len(addresses)} nodes. "
            f"Scores converted from [0.0, 1.0] to basis points [0, 10000]. "
            f"Threshold: {threshold_applied}. "
            "STUB: transaction drafted but not submitted."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload=chain_update_result,
    )

    return {
        **state,
        "current_threshold": threshold_applied,
        "chain_update_result": chain_update_result,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTING
# ═══════════════════════════════════════════════════════════════════════════════


def _route_after_threshold(state: StewardshipCouncilState) -> str:
    """Route to HITL if threshold change requires approval."""
    if state.get("requires_human_token"):
        return "human_review_threshold"
    return "push_scores_to_chain"


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH ASSEMBLY
# ═══════════════════════════════════════════════════════════════════════════════


def build_stewardship_scorer_graph():
    """Compile the Stewardship Scorer LangGraph.

    Flow:
      aggregate_contributions → fetch_ethical_audit → compute_impact_scores
        → evaluate_steward_eligibility → propose_threshold_update
        → [HITL if threshold change] → push_scores_to_chain → END
    """
    g = StateGraph(StewardshipCouncilState)
    g.add_node("aggregate_contributions", aggregate_contributions)
    g.add_node("fetch_ethical_audit", fetch_ethical_audit)
    g.add_node("compute_impact_scores", compute_impact_scores)
    g.add_node("evaluate_steward_eligibility", evaluate_steward_eligibility)
    g.add_node("propose_threshold_update", propose_threshold_update)
    g.add_node("human_review_threshold", human_review_threshold)
    g.add_node("push_scores_to_chain", push_scores_to_chain)

    g.set_entry_point("aggregate_contributions")
    g.add_edge("aggregate_contributions", "fetch_ethical_audit")
    g.add_edge("fetch_ethical_audit", "compute_impact_scores")
    g.add_edge("compute_impact_scores", "evaluate_steward_eligibility")
    g.add_edge("evaluate_steward_eligibility", "propose_threshold_update")
    g.add_conditional_edges(
        "propose_threshold_update",
        _route_after_threshold,
        {
            "human_review_threshold": "human_review_threshold",
            "push_scores_to_chain": "push_scores_to_chain",
        },
    )
    g.add_edge("human_review_threshold", "push_scores_to_chain")
    g.add_edge("push_scores_to_chain", END)

    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_review_threshold"],
    )


stewardship_scorer_graph = build_stewardship_scorer_graph()
