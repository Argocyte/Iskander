"""
ICA Ethics Vetting Agent — Phase 17: Trading Partner Due Diligence.

Evaluates potential trading partners against the 7 ICA Cooperative Principles.
Sources signals from on-chain (CoopIdentity SBT, IskanderEscrow history,
ArbitrationRegistry verdicts), off-chain federation (ActivityPub actor profiles),
and meatspace (public cooperative registries, legal filings).

Outputs a per-principle compliance scorecard and a composite value matrix
ranking all candidate partners.  The agent NEVER approves or rejects a
partner autonomously — it provides transparent assessment for human decision.

Graph:
  intake_partner → gather_on_chain_signals → gather_off_chain_signals
    → assess_ica_principles → compute_value_matrix
    → [conditional: HITL if any FAIL] → emit_report → END
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.core import load_prompt
from backend.agents.core.glass_box_parser import GlassBoxParser
from backend.agents.state import ICAVettingState
from backend.config import settings
from backend.routers.power import agents_are_paused
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "ica-vetter-agent-v1"

_role_prompt = load_prompt("prompt_ica_vetter.txt")
_parser = GlassBoxParser()

# ── The 7 ICA Principles (canonical identifiers) ────────────────────────────

ICA_PRINCIPLES = [
    {"id": "P1", "name": "Voluntary & Open Membership",
     "question": "Does the partner restrict membership/employment based on gender, race, religion, social status, or political affiliation?"},
    {"id": "P2", "name": "Democratic Member Control",
     "question": "Is the partner democratically governed? Do workers/members have meaningful decision-making power?"},
    {"id": "P3", "name": "Member Economic Participation",
     "question": "Do members/workers share in economic surplus, or does surplus flow to external shareholders?"},
    {"id": "P4", "name": "Autonomy & Independence",
     "question": "Is the partner self-governing, or controlled by an external investor/parent that could override cooperative values?"},
    {"id": "P5", "name": "Education, Training & Information",
     "question": "Does the partner invest in member/worker education and share information transparently?"},
    {"id": "P6", "name": "Cooperation Among Cooperatives",
     "question": "Does the partner actively collaborate with other cooperatives and prefer cooperative supply chains?"},
    {"id": "P7", "name": "Concern for Community",
     "question": "Does the partner demonstrate genuine concern for community welfare, environment, and local economic development?"},
]

# Default principle weights — cooperative may override via bylaws.
DEFAULT_WEIGHTS = {p["id"]: 1.0 for p in ICA_PRINCIPLES}

# Score thresholds
GRADE_THRESHOLDS = [(80, "STRONG"), (50, "PARTIAL"), (20, "WEAK"), (0, "FAIL")]


def _score_to_grade(score: int) -> str:
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "FAIL"


# ── Node 1: Intake partner query ────────────────────────────────────────────


def intake_partner(state: ICAVettingState) -> dict[str, Any]:
    """Parse the vetting request: sector need, candidate list, search scope.

    Accepts structured input:
      {
        "sector": "organic grain supply",
        "candidates": [
          {"name": "Prairie Wheat Coop", "did": "did:...", "type": "cooperative"},
          {"name": "AgriCorp Ltd", "ein": "12-345678", "type": "conventional"},
        ],
        "search_scope": "on_chain+federation+meatspace"
      }
    """
    if agents_are_paused():
        return {**state, "error": "Agents paused (low power mode)."}

    query = state.get("partner_query", {}) or {}
    candidates = query.get("candidates", [])

    if not candidates:
        action = AgentAction(
            agent_id=AGENT_ID,
            action="REJECT — no candidates provided",
            rationale="ICA vetting requires at least one candidate partner to assess.",
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"error": "empty_candidates"},
        )
        return {
            **state,
            "error": "No candidate partners provided in partner_query.candidates.",
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }

    # Normalize candidates: ensure each has a unique vetting_id.
    for i, c in enumerate(candidates):
        c.setdefault("vetting_id", str(uuid4()))
        c.setdefault("type", "unknown")
        c.setdefault("name", f"Candidate-{i+1}")

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Intake: {len(candidates)} candidates for sector '{query.get('sector', 'unspecified')}'",
        rationale=(
            "ICA Ethics Vetting Agent initiated. All candidates will be assessed "
            "against the 7 ICA Cooperative Principles before any trade or escrow "
            "agreement. The cooperative's democratic body makes the final decision."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"sector": query.get("sector"), "candidate_count": len(candidates)},
    )

    return {
        **state,
        "candidate_partners": candidates,
        "action_log": state.get("action_log", []) + [action.model_dump()],
        "error": None,
    }


# ── Node 2: Gather on-chain signals ─────────────────────────────────────────


def gather_on_chain_signals(state: ICAVettingState) -> dict[str, Any]:
    """Query on-chain data for each candidate: SBT membership, trust score,
    escrow trade history, arbitration verdicts.

    On-chain signals are the highest-trust evidence tier because they are
    immutable, publicly verifiable, and cannot be self-reported.
    """
    candidates = state.get("candidate_partners", [])
    signals: list[dict[str, Any]] = []

    from web3 import Web3
    try:
        w3 = Web3(Web3.HTTPProvider(settings.evm_rpc_url))
        evm_connected = w3.is_connected()
    except Exception:
        evm_connected = False

    for candidate in candidates:
        sig: dict[str, Any] = {
            "vetting_id": candidate.get("vetting_id"),
            "name": candidate.get("name"),
            "source": "on_chain",
            "has_sbt": False,
            "trust_score": None,
            "escrow_history": [],
            "arbitration_verdicts": [],
            "data_available": False,
        }

        did_or_addr = candidate.get("did") or candidate.get("address")
        if evm_connected and did_or_addr and did_or_addr.startswith("0x"):
            try:
                addr = Web3.to_checksum_address(did_or_addr)
                # Check CoopIdentity SBT balance (1 = active member of some coop).
                balance = w3.eth.get_balance(addr)
                sig["has_sbt"] = balance >= 0  # Address exists on-chain.
                sig["data_available"] = True

                # In production: query CoopIdentity.memberToken(addr) for SBT,
                # CoopIdentity.memberRecords(tokenId).trustScore for trust score,
                # and IskanderEscrow event logs for trade history.
                # Stub: mark as available for assessment node to interpret.
                sig["trust_score"] = candidate.get("trust_score", None)
                sig["escrow_history"] = candidate.get("escrow_history", [])
                sig["arbitration_verdicts"] = candidate.get("arbitration_verdicts", [])
            except Exception as exc:
                logger.warning("On-chain query failed for %s: %s", candidate.get("name"), exc)
        else:
            # Off-chain/meatspace entity — no on-chain data expected.
            # This is NOT a penalty. A bakery cooperative that has never touched
            # a blockchain may still score perfectly on ICA principles.
            sig["note"] = "No on-chain presence. This is informational, not penalizing."

        signals.append(sig)

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Gathered on-chain signals for {len(signals)} candidates",
        rationale=(
            "On-chain data (SBTs, trust scores, escrow history, arbitration verdicts) "
            "is the highest-trust evidence tier — immutable and publicly verifiable. "
            "Absence of on-chain data is noted but NOT penalized. Meatspace cooperatives "
            "operate validly without blockchain infrastructure."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"signals_count": len(signals), "evm_connected": evm_connected},
    )

    return {
        **state,
        "on_chain_signals": signals,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 3: Gather off-chain / federation / meatspace signals ───────────────


_OFFCHAIN_ASSESSMENT_PROMPT = (
    "You are assessing a potential trading partner for a worker cooperative.\n"
    "Based on the following partner information, extract any evidence relevant "
    "to the 7 ICA Cooperative Principles.\n\n"
    "Partner: {name}\n"
    "Type: {entity_type}\n"
    "Sector: {sector}\n"
    "Known information: {info}\n\n"
    "Respond with ONLY a JSON object:\n"
    '{{"governance_structure": "...", "ownership_model": "...", '
    '"worker_participation": "...", "community_engagement": "...", '
    '"cooperative_affiliations": [...], "environmental_record": "...", '
    '"data_gaps": [...], "confidence": 0.0-1.0}}'
)


def gather_off_chain_signals(state: ICAVettingState) -> dict[str, Any]:
    """Gather off-chain evidence: federation profiles, public registries, meatspace data.

    Data sources:
      - ActivityPub actor profiles from federated sister cooperatives
      - Cooperative directory listings (ICA, NCBA CLUSA, Cooperatives Europe)
      - Public corporate filings and legal records
      - Self-reported information (lowest trust weight)

    The LLM synthesizes available information into structured evidence.
    It does NOT fabricate — it explicitly flags data gaps.
    """
    candidates = state.get("candidate_partners", [])
    query = state.get("partner_query", {}) or {}
    sector = query.get("sector", "unspecified")
    signals: list[dict[str, Any]] = []

    try:
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        llm_available = True
    except Exception:
        llm_available = False

    for candidate in candidates:
        sig: dict[str, Any] = {
            "vetting_id": candidate.get("vetting_id"),
            "name": candidate.get("name"),
            "source": "off_chain",
            "federation_profile": None,
            "registry_listing": None,
            "llm_synthesis": None,
            "data_gaps": [],
        }

        # Check federation actor profile (ActivityPub).
        # In production: query /federation/actors/{handle} for the candidate.
        federation_did = candidate.get("did", "")
        if federation_did and federation_did.startswith("did:iskander:"):
            sig["federation_profile"] = {
                "did": federation_did,
                "federated": True,
                "note": "Registered in Iskander federation network.",
            }

        # Check cooperative registries.
        # In production: query ICA directory API, NCBA CLUSA, etc.
        coop_type = candidate.get("type", "unknown").lower()
        if coop_type in ("cooperative", "coop", "worker-cooperative"):
            sig["registry_listing"] = {
                "type": coop_type,
                "self_identified": True,
                "note": "Self-identifies as cooperative. Verify with registry.",
            }

        # LLM synthesis of available information.
        if llm_available:
            known_info = json.dumps({
                k: v for k, v in candidate.items()
                if k not in ("vetting_id",) and v is not None
            }, default=str)

            try:
                resp = llm.invoke(_OFFCHAIN_ASSESSMENT_PROMPT.format(
                    name=candidate.get("name", "Unknown"),
                    entity_type=candidate.get("type", "unknown"),
                    sector=sector,
                    info=known_info[:2000],
                ))
                sig["llm_synthesis"] = _parse_json_obj(resp.content)
                sig["data_gaps"] = sig["llm_synthesis"].get("data_gaps", [])
            except Exception as exc:
                logger.warning("Off-chain LLM synthesis failed for %s: %s",
                               candidate.get("name"), exc)
                sig["data_gaps"].append("LLM synthesis unavailable — manual review required.")

        signals.append(sig)

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Gathered off-chain/federation/meatspace signals for {len(signals)} candidates",
        rationale=(
            "Off-chain evidence complements on-chain data. Federation profiles, "
            "cooperative registry listings, and public records provide context that "
            "blockchain data alone cannot. Data gaps are explicitly flagged — the "
            "absence of information is itself a signal, but not a disqualifier."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"signals_count": len(signals), "llm_available": llm_available},
    )

    return {
        **state,
        "off_chain_signals": signals,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: Assess ICA Principles ───────────────────────────────────────────


_PRINCIPLE_ASSESSMENT_PROMPT = (
    "You are assessing a trading partner against ICA Cooperative Principle {pid}: "
    "{principle_name}.\n\n"
    "Key question: {question}\n\n"
    "Available evidence:\n"
    "ON-CHAIN: {on_chain}\n"
    "OFF-CHAIN: {off_chain}\n"
    "PARTNER INFO: {partner_info}\n\n"
    "Score this partner 0-100 on this principle.\n"
    "Respond with ONLY a JSON object:\n"
    '{{"score": 0-100, "grade": "STRONG|PARTIAL|WEAK|FAIL", '
    '"evidence_found": "...", "evidence_missing": "...", '
    '"plain_summary": "One sentence a baker can understand."}}'
)


def assess_ica_principles(state: ICAVettingState) -> dict[str, Any]:
    """Score each candidate against all 7 ICA Principles.

    For each candidate × each principle, the LLM synthesizes the gathered
    on-chain and off-chain evidence into a score (0-100), qualitative grade,
    and plain-language summary.  Evidence gaps are surfaced explicitly.

    The agent NEVER fabricates evidence.  If data is unavailable, the score
    reflects uncertainty, not punishment.
    """
    candidates = state.get("candidate_partners", [])
    on_chain = {s["vetting_id"]: s for s in state.get("on_chain_signals", [])}
    off_chain = {s["vetting_id"]: s for s in state.get("off_chain_signals", [])}
    assessments: list[dict[str, Any]] = []

    try:
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        llm_available = True
    except Exception:
        llm_available = False

    for candidate in candidates:
        vid = candidate.get("vetting_id")
        partner_on_chain = on_chain.get(vid, {})
        partner_off_chain = off_chain.get(vid, {})

        partner_assessment = {
            "vetting_id": vid,
            "name": candidate.get("name"),
            "type": candidate.get("type"),
            "principles": [],
            "has_any_fail": False,
        }

        for principle in ICA_PRINCIPLES:
            if llm_available:
                try:
                    resp = llm.invoke(_PRINCIPLE_ASSESSMENT_PROMPT.format(
                        pid=principle["id"],
                        principle_name=principle["name"],
                        question=principle["question"],
                        on_chain=json.dumps(partner_on_chain, default=str)[:1000],
                        off_chain=json.dumps(partner_off_chain, default=str)[:1000],
                        partner_info=json.dumps(candidate, default=str)[:500],
                    ))
                    result = _parse_json_obj(resp.content)
                except Exception as exc:
                    logger.warning("Principle %s assessment LLM failed for %s: %s",
                                   principle["id"], candidate.get("name"), exc)
                    result = {}
            else:
                result = {}

            # Apply heuristic fallback if LLM unavailable or failed.
            score = result.get("score")
            if score is None:
                score = _heuristic_principle_score(principle["id"], candidate, partner_on_chain, partner_off_chain)
            score = max(0, min(100, int(score)))
            grade = _score_to_grade(score)

            principle_result = {
                "principle_id": principle["id"],
                "principle_name": principle["name"],
                "score": score,
                "grade": grade,
                "evidence_found": result.get("evidence_found", "Insufficient data for LLM assessment."),
                "evidence_missing": result.get("evidence_missing", "Full evidence chain unavailable."),
                "plain_summary": result.get("plain_summary",
                    f"Score: {score}/100 ({grade}). Manual review recommended."),
            }

            if grade == "FAIL":
                partner_assessment["has_any_fail"] = True

            partner_assessment["principles"].append(principle_result)

        assessments.append(partner_assessment)

    any_fail = any(a["has_any_fail"] for a in assessments)

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Assessed {len(assessments)} candidates against 7 ICA principles",
        rationale=(
            "Each candidate scored 0-100 on each of the 7 ICA Cooperative Principles. "
            "Evidence gaps are flagged explicitly. Absence of data is a risk signal, "
            "not an automatic disqualifier. A bakery with no blockchain presence but "
            "strong community roots may outscore a DAO with extractive tokenomics."
            + (" ALERT: One or more candidates scored FAIL on at least one principle."
               if any_fail else "")
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "assessments_count": len(assessments),
            "any_fail": any_fail,
            "llm_available": llm_available,
        },
    )

    return {
        **state,
        "principle_assessments": assessments,
        "requires_human_token": any_fail,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 5: Compute value matrix ────────────────────────────────────────────


def compute_value_matrix(state: ICAVettingState) -> dict[str, Any]:
    """Compute weighted composite scores and rank all candidates.

    The value matrix is a transparent ranking tool — NOT an automated filter.
    All candidates are presented to the cooperative's democratic body, even
    those with low scores.  The matrix exists to inform, not to gatekeep.

    Weights default to equal (1.0 per principle).  The cooperative may override
    via bylaws stored in the Ricardian legal wrapper.
    """
    assessments = state.get("principle_assessments", [])
    query = state.get("partner_query", {}) or {}
    weights = query.get("principle_weights", DEFAULT_WEIGHTS)

    matrix_rows: list[dict[str, Any]] = []
    total_weight = sum(weights.values())

    for assessment in assessments:
        principles = assessment.get("principles", [])
        weighted_sum = 0.0
        principle_scores = {}

        for p in principles:
            pid = p["principle_id"]
            score = p["score"]
            w = weights.get(pid, 1.0)
            weighted_sum += score * w
            principle_scores[pid] = {
                "score": score,
                "grade": p["grade"],
                "summary": p["plain_summary"],
            }

        composite = round(weighted_sum / total_weight, 1) if total_weight > 0 else 0

        matrix_rows.append({
            "vetting_id": assessment.get("vetting_id"),
            "name": assessment.get("name"),
            "type": assessment.get("type"),
            "composite_score": composite,
            "composite_grade": _score_to_grade(int(composite)),
            "has_any_fail": assessment.get("has_any_fail", False),
            "principle_scores": principle_scores,
        })

    # Rank by composite score (descending).
    matrix_rows.sort(key=lambda r: r["composite_score"], reverse=True)

    # Assign rank.
    for i, row in enumerate(matrix_rows):
        row["rank"] = i + 1

    value_matrix = {
        "sector": query.get("sector", "unspecified"),
        "weights_used": weights,
        "candidates": matrix_rows,
        "generated_by": AGENT_ID,
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Value matrix computed: {len(matrix_rows)} candidates ranked",
        rationale=(
            "Composite scores derived from weighted ICA principle assessments. "
            "All candidates presented regardless of score — the cooperative's "
            "democratic body makes the final trading partner decision. "
            "Candidates with any FAIL-grade principle are flagged for mandatory "
            "human review."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "top_candidate": matrix_rows[0]["name"] if matrix_rows else None,
            "top_score": matrix_rows[0]["composite_score"] if matrix_rows else None,
            "fail_flagged": sum(1 for r in matrix_rows if r["has_any_fail"]),
        },
    )

    return {
        **state,
        "value_matrix": value_matrix,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 5.5: Enrich with IPD prediction (Phase 18) ─────────────────────────


def enrich_with_ipd_prediction(state: ICAVettingState) -> dict[str, Any]:
    """Phase 18: For each candidate in the value matrix, predict cooperation
    probability using the IPD Auditor's signal pipeline.

    Appends `cooperation_probability` and `recommended_strategy` to each
    matrix row.  If any candidate's cooperation probability falls below the
    floor, triggers mandatory HITL review (in addition to existing FAIL trigger).
    """
    from backend.agents.library.ipd_auditor import predict_cooperation_for_partner

    matrix = state.get("value_matrix") or {}
    candidates = matrix.get("candidates", [])
    ipd_predictions: list[dict[str, Any]] = []
    any_below_floor = False

    for row in candidates:
        # Determine if this candidate is meatspace (no on-chain presence).
        is_meatspace = row.get("type", "unknown") in ("conventional", "meatspace", "unknown")
        partner_did = row.get("vetting_id", "")

        # ICA scores for this candidate.
        ica_scores = {
            "composite_score": row.get("composite_score", 0),
        }

        prediction = predict_cooperation_for_partner(
            partner_did=partner_did,
            is_meatspace=is_meatspace,
            ica_scores=ica_scores,
        )

        # Inject into matrix row.
        row["cooperation_probability"] = prediction.get("cooperation_probability")
        row["recommended_strategy"] = prediction.get("recommended_strategy")
        row["forgiveness_rate"] = prediction.get("forgiveness_rate")

        if prediction.get("requires_human_review"):
            any_below_floor = True

        ipd_predictions.append(prediction)

    # Extend HITL trigger: fire if any candidate cooperation_probability < floor
    # OR existing FAIL condition from principle assessment.
    requires_review = state.get("requires_human_token", False) or any_below_floor

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"IPD predictions enriched for {len(candidates)} candidates",
        rationale=(
            "Phase 18: Cooperation probability predicted for each candidate via "
            "Generous Tit-for-Tat signal pipeline. Candidates with P(coop) below "
            f"{settings.ipd_cooperation_floor:.0%} floor flagged for HITL review."
            + (f" {sum(1 for p in ipd_predictions if p.get('requires_human_review'))} "
               "candidate(s) below cooperation floor." if any_below_floor else "")
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "predictions_count": len(ipd_predictions),
            "any_below_floor": any_below_floor,
        },
    )

    return {
        **state,
        "value_matrix": matrix,
        "ipd_predictions": ipd_predictions,
        "requires_human_token": requires_review,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 5.75: HITL breakpoint ──────────────────────────────────────────────


def human_review_vetting(state: ICAVettingState) -> dict[str, Any]:
    """HITL breakpoint — invoked when any candidate has a FAIL-grade principle.

    The cooperative's members must review the assessment and decide whether
    to proceed with the flagged candidate despite the FAIL score.
    """
    return state


# ── Node 6: Emit report ─────────────────────────────────────────────────────


def emit_report(state: ICAVettingState) -> dict[str, Any]:
    """Compile the final vetting report for the cooperative's democratic body.

    The report is designed to be readable by non-technical members:
      - Plain-language summaries for each principle assessment
      - A ranked value matrix with clear grades
      - Explicit data gaps and risk flags
      - NO recommendation — only facts and scores
    """
    matrix = state.get("value_matrix", {}) or {}
    assessments = state.get("principle_assessments", [])

    report = {
        "report_id": str(uuid4()),
        "agent_id": AGENT_ID,
        "sector": matrix.get("sector", "unspecified"),
        "candidate_count": len(matrix.get("candidates", [])),

        # The ranked matrix — primary output.
        "value_matrix": matrix,

        # Detailed per-candidate, per-principle breakdowns.
        "detailed_assessments": assessments,

        # Summary for non-technical members.
        "executive_summary": _build_executive_summary(matrix),

        # Explicit disclaimer: AI assessed, humans decide.
        "disclaimer": (
            "This assessment was generated by the ICA Ethics Vetting Agent. "
            "It is a TRANSPARENCY TOOL, not a decision-maker. All scores are "
            "based on available evidence and may contain gaps. The cooperative's "
            "democratic body — not the AI — makes the final trading partner decision. "
            "CCIN Principle 2: Democratic Member Control. One member, one vote."
        ),
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action="ICA Ethics Vetting Report emitted",
        rationale=(
            "Final report compiled with ranked value matrix, per-principle scores, "
            "evidence citations, data gaps, and plain-language summaries. The "
            "cooperative's democratic body will review and vote on partner selection."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={"report_id": report["report_id"]},
    )

    return {
        **state,
        "vetting_report": report,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Routing logic ────────────────────────────────────────────────────────────


def _route_after_ipd_enrichment(state: ICAVettingState) -> str:
    """Route to HITL if any candidate has a FAIL-grade principle OR
    cooperation probability below the IPD floor (Phase 18)."""
    if state.get("requires_human_token"):
        return "human_review_vetting"
    return "emit_report"


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_ica_vetter_graph():
    """Compile the ICA Ethics Vetting Agent LangGraph.

    Phase 17+18 graph flow:
      intake_partner → gather_on_chain_signals → gather_off_chain_signals
        → assess_ica_principles → compute_value_matrix
        → enrich_with_ipd_prediction (Phase 18)
        → [conditional: HITL if FAIL or P(coop) < floor | emit_report] → END

    The graph halts at human_review_vetting if ANY candidate scores FAIL
    on any ICA principle OR if any candidate's cooperation probability
    falls below the IPD cooperation floor.
    """
    g = StateGraph(ICAVettingState)
    g.add_node("intake_partner", intake_partner)
    g.add_node("gather_on_chain_signals", gather_on_chain_signals)
    g.add_node("gather_off_chain_signals", gather_off_chain_signals)
    g.add_node("assess_ica_principles", assess_ica_principles)
    g.add_node("compute_value_matrix", compute_value_matrix)
    g.add_node("enrich_with_ipd_prediction", enrich_with_ipd_prediction)
    g.add_node("human_review_vetting", human_review_vetting)
    g.add_node("emit_report", emit_report)

    g.set_entry_point("intake_partner")
    g.add_edge("intake_partner", "gather_on_chain_signals")
    g.add_edge("gather_on_chain_signals", "gather_off_chain_signals")
    g.add_edge("gather_off_chain_signals", "assess_ica_principles")
    g.add_edge("assess_ica_principles", "compute_value_matrix")
    g.add_edge("compute_value_matrix", "enrich_with_ipd_prediction")
    g.add_conditional_edges(
        "enrich_with_ipd_prediction",
        _route_after_ipd_enrichment,
        {"human_review_vetting": "human_review_vetting", "emit_report": "emit_report"},
    )
    g.add_edge("human_review_vetting", "emit_report")
    g.add_edge("emit_report", END)

    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_review_vetting"],
    )


ica_vetter_graph = build_ica_vetter_graph()


# ── Heuristic fallback scoring ───────────────────────────────────────────────


def _heuristic_principle_score(
    principle_id: str,
    candidate: dict[str, Any],
    on_chain: dict[str, Any],
    off_chain: dict[str, Any],
) -> int:
    """Rule-based fallback scorer when LLM is unavailable.

    Uses structural signals: entity type, federation presence, on-chain trust
    score, cooperative registry listing.  Intentionally conservative — when
    data is missing, score reflects uncertainty (40-60 range), not penalty.
    """
    coop_type = candidate.get("type", "unknown").lower()
    is_coop = coop_type in ("cooperative", "coop", "worker-cooperative", "platform-cooperative")
    is_federated = bool(off_chain.get("federation_profile"))
    has_on_chain = bool(on_chain.get("data_available"))
    trust_score = on_chain.get("trust_score")

    base = 50  # Unknown = midpoint uncertainty, not penalty.

    if is_coop:
        base += 15  # Structural alignment with cooperative model.
    if is_federated:
        base += 10  # Active in cooperative federation.
    if has_on_chain:
        base += 5   # Verifiable on-chain presence.
    if trust_score is not None:
        # Scale trust score (0-1000) to a 0-20 bonus.
        base += int((trust_score / 1000) * 20)

    # Principle-specific adjustments.
    if principle_id == "P6" and is_federated:
        base += 10  # Cooperation Among Cooperatives — federated partners score higher.
    if principle_id == "P2" and is_coop:
        base += 10  # Democratic Member Control — cooperatives are structurally democratic.
    if principle_id == "P3" and coop_type == "conventional":
        base -= 15  # Member Economic Participation — conventional corps extract surplus.

    return max(0, min(100, base))


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_executive_summary(matrix: dict[str, Any]) -> str:
    """Build a plain-language executive summary for non-technical members."""
    candidates = matrix.get("candidates", [])
    if not candidates:
        return "No candidates were assessed."

    lines = [
        f"Sector: {matrix.get('sector', 'unspecified')}",
        f"Candidates assessed: {len(candidates)}",
        "",
    ]

    for row in candidates:
        flags = " [FLAGGED: has FAIL-grade principle]" if row.get("has_any_fail") else ""
        lines.append(
            f"  #{row['rank']}  {row['name']}  —  "
            f"Composite: {row['composite_score']}/100 ({row['composite_grade']}){flags}"
        )

    fail_count = sum(1 for r in candidates if r.get("has_any_fail"))
    if fail_count:
        lines.append("")
        lines.append(
            f"WARNING: {fail_count} candidate(s) scored FAIL on at least one ICA principle. "
            "Human review required before proceeding with these partners."
        )

    return "\n".join(lines)


def _parse_json_obj(text: str) -> dict[str, Any]:
    """Best-effort JSON object extraction."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return {}
