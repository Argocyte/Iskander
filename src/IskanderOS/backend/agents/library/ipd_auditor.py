"""
IPD Auditor Agent — Phase 18: Game-Theoretic Cooperation Prediction & Auditing.

Models every inter-coop trade as a round in an infinitely repeated Prisoner's
Dilemma. Two LangGraph StateGraphs share the IPDAuditState type:

PRE-TRADE GRAPH (7 nodes):
  load_interaction_history → compute_cooperation_signals
    → predict_cooperation_probability → compute_payoff_matrix
    → select_strategy → [HITL if P(coop) < floor] → emit_ipd_report → END

POST-TRADE GRAPH (4 nodes):
  classify_escrow_outcome → update_reputation_graph
    → compute_updated_probability → broadcast_audit_summary → END

Strategy: Generous Tit-for-Tat (GTfT).
  Start cooperative. Mirror partner's last move. Forgive defections with
  probability `ipd_forgiveness_rate`. Prevents death spirals from noise.

DESIGN CONSTRAINTS:
  - No autonomous retaliation: predicts and recommends; human cooperative votes.
  - Anti-wealth-bias: meatspace partners score equally via soft signals.
  - Off-chain reputation only: on-chain trust writes belong to ArbitrationRegistry.
  - Glass Box Protocol: every action discloses rationale + payoff matrix.
"""
from __future__ import annotations

import logging
import random
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.core import load_prompt
from backend.agents.state import IPDAuditState
from backend.config import settings
from backend.routers.power import agents_are_paused
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "ipd-auditor-agent-v1"

_role_prompt = load_prompt("prompt_ipd_auditor.txt")


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-TRADE GRAPH NODES
# ═══════════════════════════════════════════════════════════════════════════════


# ── Node 1: Load interaction history ─────────────────────────────────────────


def load_interaction_history(state: IPDAuditState) -> dict[str, Any]:
    """Query interaction_history, pairwise_cooperation, reputation_scores,
    peer_attestations, and trust_score_history for the target partner.

    STUB: In production, these are asyncpg queries against the Phase 18 tables.
    Currently returns empty/default values to enable graph compilation.
    """
    if agents_are_paused():
        return {**state, "error": "Agents paused (low power mode)."}

    partner_did = state.get("partner_did")
    if not partner_did:
        return {
            **state,
            "error": "No partner_did provided.",
            "action_log": state.get("action_log", []) + [AgentAction(
                agent_id=AGENT_ID,
                action="REJECT — no partner_did",
                rationale="IPD audit requires a partner DID to assess.",
                ethical_impact=EthicalImpactLevel.LOW,
                payload={"error": "missing_partner_did"},
            ).model_dump()],
        }

    is_meatspace = state.get("is_meatspace", False)

    # STUB: Replace with asyncpg queries.
    # SELECT * FROM interaction_history WHERE node_a=$1 OR node_b=$1
    pairwise_history: list[dict[str, Any]] = []
    # SELECT * FROM reputation_scores WHERE node_did=$1
    global_reputation: dict[str, Any] | None = None
    # SELECT * FROM trust_score_history WHERE member_did=$1 ORDER BY recorded_at DESC LIMIT 5
    trust_trajectory: list[dict[str, Any]] = []
    # SELECT * FROM peer_attestations WHERE subject_did=$1
    attestations: list[dict[str, Any]] = []

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Loaded interaction history for {partner_did[:20]}...",
        rationale=(
            "Queried pairwise trade history, global reputation, on-chain trust "
            "trajectory, and peer attestations. Data gaps are expected for "
            "first-time or meatspace partners — this is informational, not penalizing."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={
            "partner_did": partner_did,
            "pairwise_records": len(pairwise_history),
            "has_global_reputation": global_reputation is not None,
            "trust_trajectory_points": len(trust_trajectory),
            "peer_attestations": len(attestations),
            "is_meatspace": is_meatspace,
        },
    )

    return {
        **state,
        "interaction_history": pairwise_history,
        "global_history": global_reputation,
        "trust_score_trajectory": trust_trajectory,
        "peer_attestations": attestations,
        "action_log": state.get("action_log", []) + [action.model_dump()],
        "error": None,
    }


# ── Node 2: Compute cooperation signals ─────────────────────────────────────


def compute_cooperation_signals(state: IPDAuditState) -> dict[str, Any]:
    """Aggregate raw history into a cooperation signal feature vector.

    Signals:
      - coop_ratio_pairwise: from interaction_history (this node pair)
      - coop_ratio_global: from reputation_scores (all partners)
      - trust_score_normalized: on-chain trust score / 1000
      - federation_responsiveness: audit compliance + response time
      - ica_composite_normalized: ICA vetting score / 100
      - meatspace_attestation_normalized: peer_attestation_avg / 100

    When is_meatspace=True, on-chain weights are redistributed to soft signals.
    """
    partner_did = state.get("partner_did", "unknown")
    is_meatspace = state.get("is_meatspace", False)
    history = state.get("interaction_history", [])
    global_rep = state.get("global_history") or {}
    trust_traj = state.get("trust_score_trajectory", [])
    attestations = state.get("peer_attestations", [])
    ica = state.get("ica_scores") or {}
    fed = state.get("federation_behavior") or {}

    # Compute pairwise cooperation ratio.
    pairwise_coop_count = sum(
        1 for h in history
        if h.get("node_b_action") == "cooperate" or h.get("node_a_action") == "cooperate"
    )
    pairwise_total = len(history)
    coop_ratio_pairwise = (
        pairwise_coop_count / pairwise_total if pairwise_total > 0 else None
    )

    # Global cooperation ratio from reputation_scores table.
    coop_ratio_global = global_rep.get("cooperation_ratio")

    # On-chain trust score normalized to [0, 1].
    trust_score_raw = None
    if trust_traj:
        trust_score_raw = trust_traj[0].get("new_score")
    trust_score_norm = trust_score_raw / 1000.0 if trust_score_raw is not None else None

    # Federation responsiveness.
    fed_responsiveness = fed.get("audit_compliance_rate")

    # ICA composite score normalized to [0, 1].
    ica_composite_norm = None
    ica_raw = ica.get("composite_score")
    if ica_raw is not None:
        ica_composite_norm = ica_raw / 100.0

    # Meatspace attestation average normalized to [0, 1].
    attestation_avg = None
    if attestations:
        attestation_avg = sum(a.get("score", 0) for a in attestations) / len(attestations) / 100.0
    elif global_rep.get("peer_attestation_avg"):
        attestation_avg = global_rep["peer_attestation_avg"] / 100.0

    signals = {
        "coop_ratio_pairwise": coop_ratio_pairwise,
        "coop_ratio_global": coop_ratio_global,
        "trust_score_normalized": trust_score_norm,
        "federation_responsiveness": fed_responsiveness,
        "ica_composite_normalized": ica_composite_norm,
        "meatspace_attestation_normalized": attestation_avg,
    }

    # Determine trust trajectory trend.
    trend = "unknown"
    if len(trust_traj) >= 3:
        scores = [t.get("new_score", 0) for t in trust_traj[:3]]
        if scores[0] > scores[-1]:
            trend = "rising"
        elif scores[0] < scores[-1]:
            trend = "declining"
        else:
            trend = "stable"

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Cooperation signals computed for {partner_did[:20]}...",
        rationale=(
            f"Feature vector aggregated from {pairwise_total} pairwise records. "
            f"Trust trajectory: {trend}. "
            f"Is meatspace: {is_meatspace}. "
            "Null signals indicate data gaps — uncertainty, not penalty."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"signals": signals, "trend": trend},
    )

    return {
        **state,
        "federation_behavior": {**(fed or {}), "signals": signals, "trend": trend},
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 3: Predict cooperation probability ─────────────────────────────────


def predict_cooperation_probability(state: IPDAuditState) -> dict[str, Any]:
    """P(coop) = weighted sum of available signals / sum of active weights.

    First-time partners with no history get the Bayesian prior (default 0.7).
    Meatspace partners redistribute on-chain weights to soft signals.
    """
    fed = state.get("federation_behavior") or {}
    signals = fed.get("signals", {})
    is_meatspace = state.get("is_meatspace", False)

    # Base weights from config.
    weights = {
        "coop_ratio_pairwise": settings.ipd_weight_pairwise,
        "coop_ratio_global": settings.ipd_weight_global,
        "trust_score_normalized": settings.ipd_weight_trust_score,
        "federation_responsiveness": settings.ipd_weight_federation,
        "ica_composite_normalized": settings.ipd_weight_ica,
        "meatspace_attestation_normalized": settings.ipd_weight_meatspace,
    }

    # Meatspace redistribution: if partner has no on-chain presence,
    # redistribute on-chain weights (trust_score, pairwise if empty) to
    # available soft signals (federation, ica, meatspace).
    if is_meatspace:
        redistributable = weights.pop("trust_score_normalized", 0.0)
        if signals.get("coop_ratio_pairwise") is None:
            redistributable += weights.pop("coop_ratio_pairwise", 0.0)
        remaining = {k: v for k, v in weights.items() if signals.get(k) is not None}
        if remaining:
            bonus = redistributable / len(remaining)
            for k in remaining:
                weights[k] = weights.get(k, 0.0) + bonus

    # Compute weighted average over available signals.
    numerator = 0.0
    denominator = 0.0
    active_signals: dict[str, float] = {}

    for signal_name, weight in weights.items():
        value = signals.get(signal_name)
        if value is not None:
            numerator += value * weight
            denominator += weight
            active_signals[signal_name] = value

    if denominator > 0:
        p_coop = numerator / denominator
    else:
        # No signals available — use Bayesian prior.
        p_coop = settings.ipd_prior_cooperation

    # Clamp to [0, 1].
    p_coop = max(0.0, min(1.0, round(p_coop, 4)))

    requires_review = p_coop < settings.ipd_cooperation_floor

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Cooperation probability: {p_coop:.2%}",
        rationale=(
            f"P(cooperate) = {p_coop:.4f} from {len(active_signals)} active signals. "
            f"{'Bayesian prior used (no history).' if not active_signals else ''} "
            f"{'HITL REQUIRED: below cooperation floor.' if requires_review else ''}"
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "cooperation_probability": p_coop,
            "active_signals": active_signals,
            "weights_used": weights,
            "prior_used": len(active_signals) == 0,
            "requires_human_review": requires_review,
        },
    )

    return {
        **state,
        "cooperation_probability": p_coop,
        "requires_human_token": requires_review,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: Compute payoff matrix ───────────────────────────────────────────


def compute_payoff_matrix(state: IPDAuditState) -> dict[str, Any]:
    """Build the PD payoff matrix and compute expected values.

    EV(cooperate) = P(coop)*R + (1-P(coop))*S
    EV(defect)    = P(coop)*T + (1-P(coop))*P
    """
    p_coop = state.get("cooperation_probability", settings.ipd_prior_cooperation)

    R = settings.ipd_payoff_r
    S = settings.ipd_payoff_s
    T = settings.ipd_payoff_t
    P = settings.ipd_payoff_p

    ev_cooperate = p_coop * R + (1 - p_coop) * S
    ev_defect = p_coop * T + (1 - p_coop) * P

    matrix = {
        "R": R, "S": S, "T": T, "P": P,
        "EV_cooperate": round(ev_cooperate, 4),
        "EV_defect": round(ev_defect, 4),
        "cooperation_probability": p_coop,
        "cooperate_dominant": ev_cooperate >= ev_defect,
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Payoff matrix computed: EV(C)={ev_cooperate:.2f}, EV(D)={ev_defect:.2f}",
        rationale=(
            f"Standard PD payoffs (R={R}, S={S}, T={T}, P={P}). "
            f"At P(coop)={p_coop:.2%}: cooperating yields EV={ev_cooperate:.2f}, "
            f"defecting yields EV={ev_defect:.2f}. "
            "Note: GTfT does not maximize single-round EV — it maximizes "
            "long-run cooperation in the infinitely repeated game."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload=matrix,
    )

    return {
        **state,
        "payoff_matrix": matrix,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 5: Select strategy (Generous Tit-for-Tat) ──────────────────────────


def select_strategy(state: IPDAuditState) -> dict[str, Any]:
    """Apply Generous Tit-for-Tat: mirror last move, forgive with probability.

    - First interaction (no history): COOPERATE.
    - Partner's last move was cooperate: COOPERATE.
    - Partner's last move was defect: COOPERATE with probability
      `ipd_forgiveness_rate`, else DEFECT.

    The forgiveness mechanism prevents mutual-defection death spirals caused
    by noise (misclassified outcomes, network errors, ambiguous escrow
    resolutions).
    """
    history = state.get("interaction_history", [])
    partner_did = state.get("partner_did", "unknown")
    forgiveness_rate = settings.ipd_forgiveness_rate

    # Determine partner's last action.
    last_partner_action = None
    if history:
        # Find the most recent interaction where this partner was involved.
        latest = history[0] if history else None
        if latest:
            # Determine which node position the partner occupies.
            if latest.get("node_b") == partner_did:
                last_partner_action = latest.get("node_b_action")
            elif latest.get("node_a") == partner_did:
                last_partner_action = latest.get("node_a_action")

    # GTfT strategy selection.
    forgiveness_rolled = False
    if last_partner_action is None:
        # First interaction — default to cooperate.
        recommended = "cooperate"
        rationale = (
            f"First interaction with {partner_did[:20]}... — GTfT defaults to "
            "COOPERATE. No history exists; the cooperative extends trust first."
        )
    elif last_partner_action == "cooperate":
        recommended = "cooperate"
        rationale = (
            f"Partner's last move was COOPERATE — GTfT mirrors: COOPERATE."
        )
    else:
        # Partner's last move was defect. Forgive with probability.
        if random.random() < forgiveness_rate:
            recommended = "cooperate"
            forgiveness_rolled = True
            rationale = (
                f"Partner's last move was DEFECT — but GTfT FORGIVES this round "
                f"(forgiveness rate: {forgiveness_rate:.0%}). Cooperating to break "
                "potential death spiral from misclassification noise."
            )
        else:
            recommended = "defect"
            rationale = (
                f"Partner's last move was DEFECT — GTfT RETALIATES this round "
                f"(forgiveness rate: {forgiveness_rate:.0%}, roll did not forgive). "
                "Retaliation maintains credibility; forgiveness will come stochastically."
            )

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"GTfT recommends: {recommended.upper()}",
        rationale=rationale,
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "recommended_strategy": recommended,
            "last_partner_action": last_partner_action,
            "forgiveness_rate": forgiveness_rate,
            "forgiveness_rolled": forgiveness_rolled,
            "strategy": settings.ipd_strategy,
        },
    )

    return {
        **state,
        "recommended_strategy": recommended,
        "strategy_rationale": rationale,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 5.5: HITL breakpoint ───────────────────────────────────────────────


def human_review_ipd(state: IPDAuditState) -> dict[str, Any]:
    """HITL breakpoint — fires when cooperation_probability < floor.

    The cooperative's democratic body must review the risk assessment and
    decide whether to proceed with this trade despite the low cooperation
    prediction.
    """
    return state


# ── Node 6: Emit IPD report ─────────────────────────────────────────────────


def emit_ipd_report(state: IPDAuditState) -> dict[str, Any]:
    """Compile the final pre-trade IPD analysis report.

    Includes: cooperation probability, payoff matrix, GTfT recommendation,
    forgiveness rate, all signals used, plain-language summary, disclaimer.
    """
    partner_did = state.get("partner_did", "unknown")
    p_coop = state.get("cooperation_probability", 0.0)
    matrix = state.get("payoff_matrix") or {}
    recommended = state.get("recommended_strategy", "cooperate")
    rationale = state.get("strategy_rationale", "")

    report = {
        "report_id": str(uuid4()),
        "agent_id": AGENT_ID,
        "partner_did": partner_did,
        "audit_mode": "pre_trade",
        "cooperation_probability": p_coop,
        "recommended_strategy": recommended,
        "strategy_rationale": rationale,
        "payoff_matrix": matrix,
        "forgiveness_rate": settings.ipd_forgiveness_rate,
        "signals_used": (state.get("federation_behavior") or {}).get("signals", {}),
        "requires_human_review": state.get("requires_human_token", False),
        "is_meatspace": state.get("is_meatspace", False),
        "risk_assessment": {
            "cooperation_floor": settings.ipd_cooperation_floor,
            "below_floor": p_coop < settings.ipd_cooperation_floor,
            "trust_trajectory": (state.get("federation_behavior") or {}).get("trend", "unknown"),
        },
        "disclaimer": (
            "This prediction is a TRANSPARENCY TOOL generated by the IPD Auditor Agent. "
            "Strategy: Generous Tit-for-Tat. The cooperative's democratic body makes "
            "the final trading decision. CCIN Principle 2: one member, one vote."
        ),
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action="IPD pre-trade report emitted",
        rationale=(
            f"Pre-trade analysis complete for {partner_did[:20]}... "
            f"P(coop)={p_coop:.2%}, GTfT recommends: {recommended}. "
            f"Forgiveness rate: {settings.ipd_forgiveness_rate:.0%}."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={"report_id": report["report_id"]},
    )

    return {
        **state,
        "ipd_report": report,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# POST-TRADE GRAPH NODES
# ═══════════════════════════════════════════════════════════════════════════════


# ── Outcome classification map ───────────────────────────────────────────────

_OUTCOME_MAP = {
    # escrow_outcome → (buyer_action, seller_action)
    "Released":   ("cooperate", "cooperate"),    # Both fulfilled
    "Expired":    ("cooperate", "defect"),        # Seller failed to deliver
    # For Arbitrated outcomes, use arbitration_outcome:
    #   buyer_favored → seller defected
    #   seller_favored → buyer defected
    #   split → reduced mutual defection
    #   dismissed → both cooperated (dispute was unfounded)
}

_ARBITRATION_MAP = {
    "buyer_favored":  ("cooperate", "defect"),
    "seller_favored": ("defect", "cooperate"),
    "split":          ("defect", "defect"),
    "dismissed":      ("cooperate", "cooperate"),
}


# ── Node P1: Classify escrow outcome ────────────────────────────────────────


def classify_escrow_outcome(state: IPDAuditState) -> dict[str, Any]:
    """Map escrow resolution to cooperate/defect per party.

    Released → (C, C).  BuyerFavored → (C, D).  SellerFavored → (D, C).
    Split → (D, D).  Dismissed → (C, C).  Expired → (C, D).
    """
    outcome = state.get("escrow_outcome") or {}
    escrow_status = outcome.get("escrow_outcome", "Released")
    arb_outcome = outcome.get("arbitration_outcome")

    if escrow_status == "Arbitrated" and arb_outcome:
        buyer_action, seller_action = _ARBITRATION_MAP.get(
            arb_outcome, ("cooperate", "cooperate")
        )
    elif escrow_status == "Disputed":
        # Disputed but not yet arbitrated — treat as pending, default (C, C).
        buyer_action, seller_action = "cooperate", "cooperate"
    else:
        buyer_action, seller_action = _OUTCOME_MAP.get(
            escrow_status, ("cooperate", "cooperate")
        )

    classification = {
        "escrow_id": outcome.get("escrow_id"),
        "escrow_outcome": escrow_status,
        "arbitration_outcome": arb_outcome,
        "buyer_did": outcome.get("buyer_did"),
        "seller_did": outcome.get("seller_did"),
        "buyer_action": buyer_action,
        "seller_action": seller_action,
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Outcome classified: buyer={buyer_action}, seller={seller_action}",
        rationale=(
            f"Escrow {outcome.get('escrow_id', '?')} resolved as '{escrow_status}'"
            f"{f' (arb: {arb_outcome})' if arb_outcome else ''}. "
            f"Buyer: {buyer_action}. Seller: {seller_action}."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload=classification,
    )

    return {
        **state,
        "outcome_classification": classification,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node P2: Update reputation graph ────────────────────────────────────────


def update_reputation_graph(state: IPDAuditState) -> dict[str, Any]:
    """INSERT into interaction_history. UPSERT pairwise_cooperation and
    reputation_scores. No on-chain trust changes.

    STUB: Logs the intended writes. Production: asyncpg transactions.
    """
    classification = state.get("outcome_classification") or {}
    buyer_did = classification.get("buyer_did", "unknown")
    seller_did = classification.get("seller_did", "unknown")
    buyer_action = classification.get("buyer_action", "cooperate")
    seller_action = classification.get("seller_action", "cooperate")
    escrow_id = classification.get("escrow_id")

    # STUB: Log intended DB operations.
    logger.info(
        "STUB: INSERT interaction_history(%s, %s, %s, %s, %s)",
        buyer_did[:15], seller_did[:15], escrow_id, buyer_action, seller_action,
    )
    logger.info(
        "STUB: UPSERT pairwise_cooperation(%s, %s) — last_a=%s, last_b=%s",
        buyer_did[:15], seller_did[:15], buyer_action, seller_action,
    )

    reputation_delta = {
        "buyer_did": buyer_did,
        "seller_did": seller_did,
        "buyer_action": buyer_action,
        "seller_action": seller_action,
        "escrow_id": escrow_id,
        "tables_updated": [
            "interaction_history",
            "pairwise_cooperation",
            "reputation_scores",
        ],
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Reputation graph updated for escrow {escrow_id}",
        rationale=(
            "Off-chain reputation tables updated with trade outcome. "
            "No on-chain trust score changes — ArbitrationRegistry handles those. "
            "This maintains the hybrid model: on-chain = hard penalties, "
            "off-chain = soft reputation signals."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload=reputation_delta,
    )

    return {
        **state,
        "reputation_update": reputation_delta,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node P3: Compute updated probability ────────────────────────────────────


def compute_updated_probability(state: IPDAuditState) -> dict[str, Any]:
    """Re-compute cooperation probability after the new data point.

    In production, this re-runs the weighted aggregation with the updated
    reputation_scores. Stub: returns the current probability unchanged.
    """
    p_coop = state.get("cooperation_probability", settings.ipd_prior_cooperation)

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Updated cooperation probability: {p_coop:.2%}",
        rationale=(
            "Cooperation probability re-computed after recording new outcome. "
            "In production, this re-queries the updated reputation_scores table."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"cooperation_probability": p_coop},
    )

    return {
        **state,
        "cooperation_probability": p_coop,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node P4: Broadcast audit summary ────────────────────────────────────────


def broadcast_audit_summary(state: IPDAuditState) -> dict[str, Any]:
    """Publish iskander:AuditSummary activity via federation outbox.

    Non-confidential summary: escrow_id, outcome classification, updated
    cooperation score, timestamp. Broadcast to federated sister cooperatives
    for network-wide transparency.

    STUB: Logs the intended broadcast. Production: call ArbitrationProtocol.
    """
    classification = state.get("outcome_classification") or {}
    p_coop = state.get("cooperation_probability", 0.0)

    summary = {
        "type": "iskander:AuditSummary",
        "escrow_id": classification.get("escrow_id"),
        "buyer_action": classification.get("buyer_action"),
        "seller_action": classification.get("seller_action"),
        "escrow_outcome": classification.get("escrow_outcome"),
        "updated_cooperation_score": p_coop,
    }

    logger.info(
        "STUB: Broadcasting AuditSummary for escrow %s via federation outbox",
        classification.get("escrow_id"),
    )

    report = {
        "report_id": str(uuid4()),
        "agent_id": AGENT_ID,
        "audit_mode": "post_trade",
        "outcome_classification": classification,
        "reputation_update": state.get("reputation_update"),
        "cooperation_probability": p_coop,
        "federation_broadcast": summary,
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Post-trade audit summary broadcast",
        rationale=(
            "Audit summary published to federation outbox for network-wide "
            "transparency. Non-confidential: escrow ID, outcome classification, "
            "updated cooperation score."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={"report_id": report["report_id"]},
    )

    return {
        **state,
        "ipd_report": report,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH ASSEMBLY
# ═══════════════════════════════════════════════════════════════════════════════


def _route_after_strategy(state: IPDAuditState) -> str:
    """Route to HITL if cooperation probability < floor."""
    if state.get("requires_human_token"):
        return "human_review_ipd"
    return "emit_ipd_report"


def build_pre_trade_graph():
    """Compile the pre-trade IPD prediction LangGraph.

    Flow:
      load_interaction_history → compute_cooperation_signals
        → predict_cooperation_probability → compute_payoff_matrix
        → select_strategy → [HITL if P(coop) < floor] → emit_ipd_report → END
    """
    g = StateGraph(IPDAuditState)
    g.add_node("load_interaction_history", load_interaction_history)
    g.add_node("compute_cooperation_signals", compute_cooperation_signals)
    g.add_node("predict_cooperation_probability", predict_cooperation_probability)
    g.add_node("compute_payoff_matrix", compute_payoff_matrix)
    g.add_node("select_strategy", select_strategy)
    g.add_node("human_review_ipd", human_review_ipd)
    g.add_node("emit_ipd_report", emit_ipd_report)

    g.set_entry_point("load_interaction_history")
    g.add_edge("load_interaction_history", "compute_cooperation_signals")
    g.add_edge("compute_cooperation_signals", "predict_cooperation_probability")
    g.add_edge("predict_cooperation_probability", "compute_payoff_matrix")
    g.add_edge("compute_payoff_matrix", "select_strategy")
    g.add_conditional_edges(
        "select_strategy",
        _route_after_strategy,
        {"human_review_ipd": "human_review_ipd", "emit_ipd_report": "emit_ipd_report"},
    )
    g.add_edge("human_review_ipd", "emit_ipd_report")
    g.add_edge("emit_ipd_report", END)

    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_review_ipd"],
    )


def build_post_trade_graph():
    """Compile the post-trade outcome recording LangGraph.

    Flow:
      classify_escrow_outcome → update_reputation_graph
        → compute_updated_probability → broadcast_audit_summary → END
    """
    g = StateGraph(IPDAuditState)
    g.add_node("classify_escrow_outcome", classify_escrow_outcome)
    g.add_node("update_reputation_graph", update_reputation_graph)
    g.add_node("compute_updated_probability", compute_updated_probability)
    g.add_node("broadcast_audit_summary", broadcast_audit_summary)

    g.set_entry_point("classify_escrow_outcome")
    g.add_edge("classify_escrow_outcome", "update_reputation_graph")
    g.add_edge("update_reputation_graph", "compute_updated_probability")
    g.add_edge("compute_updated_probability", "broadcast_audit_summary")
    g.add_edge("broadcast_audit_summary", END)

    return g.compile(checkpointer=MemorySaver())


pre_trade_graph = build_pre_trade_graph()
post_trade_graph = build_post_trade_graph()


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTED HELPER — used by ICA Vetter enrichment and API router
# ═══════════════════════════════════════════════════════════════════════════════


def predict_cooperation_for_partner(
    partner_did: str,
    is_meatspace: bool = False,
    ica_scores: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Synchronous helper: predict cooperation probability without running
    the full LangGraph. Used by enrich_with_ipd_prediction in ica_vetter.py
    and the /ipd-audit/predict API endpoint.

    Returns a dict with cooperation_probability, recommended_strategy,
    strategy_rationale, payoff_matrix, forgiveness_rate, requires_human_review.
    """
    # Build a minimal state and run through the signal pipeline.
    state: dict[str, Any] = {
        "messages": [],
        "agent_id": AGENT_ID,
        "action_log": [],
        "error": None,
        "partner_did": partner_did,
        "audit_mode": "pre_trade",
        "interaction_history": [],
        "global_history": None,
        "trust_score_trajectory": [],
        "federation_behavior": None,
        "ica_scores": ica_scores,
        "cooperation_probability": None,
        "payoff_matrix": None,
        "recommended_strategy": None,
        "strategy_rationale": None,
        "risk_assessment": None,
        "escrow_outcome": None,
        "outcome_classification": None,
        "reputation_update": None,
        "audit_request": None,
        "audit_response": None,
        "ipd_report": None,
        "requires_human_token": False,
        "is_meatspace": is_meatspace,
        "peer_attestations": [],
    }

    # Run signal pipeline (no DB queries in stub — returns defaults/priors).
    state = load_interaction_history(state)
    state = compute_cooperation_signals(state)
    state = predict_cooperation_probability(state)
    state = compute_payoff_matrix(state)
    state = select_strategy(state)

    return {
        "partner_did": partner_did,
        "cooperation_probability": state.get("cooperation_probability", settings.ipd_prior_cooperation),
        "recommended_strategy": state.get("recommended_strategy", "cooperate"),
        "strategy_rationale": state.get("strategy_rationale", ""),
        "payoff_matrix": state.get("payoff_matrix", {}),
        "forgiveness_rate": settings.ipd_forgiveness_rate,
        "requires_human_review": state.get("requires_human_token", False),
        "is_meatspace": is_meatspace,
    }
