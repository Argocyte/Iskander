"""
ritl_manager.py — Researcher-in-the-Loop (RITL) Peer Review Graph.

A LangGraph StateGraph implementing structured peer review for knowledge
assets entering the Iskander Knowledge Commons. Three specialized reviewer
agents evaluate submissions across four dimensions (Rigor, Novelty, Ethics,
Reproducibility), followed by a Socratic Cross-Examination dialectic where
reviewers challenge each other's assessments.

GRAPH ARCHITECTURE:
    validate_submission
      → assign_reviewers
      → rigor_review
      → novelty_review
      → ethics_review
      → reproducibility_review
      → socratic_cross_examination
      → evaluate_consensus
      → [CONDITIONAL:
           accept → finalize_admission → END
           minor/major_revisions → human_review_research (HITL) → finalize_admission → END
           reject → END]

SOCRATIC CROSS-EXAMINATION:
    After all reviews, the cross-examination node generates questions from
    each reviewer directed at the others' weakest arguments. This dialectic
    transcript is pinned to the Mesh Archive as a CausalEvent for permanent
    audit trail.

BLIND REVIEW (ZK-flow):
    When ``blind_mode=True``, reviewer identities are masked in the output.
    The Glass Box audit trail still records the real agent IDs internally,
    but the submission author and external observers see only anonymized
    reviewer labels (Reviewer-A, Reviewer-B, etc.).

REUSE:
    - CuratorNetwork pattern: graph nodes, consensus logic, HITL interrupt
    - CausalEvent: for pinning dialectic transcripts
    - LibraryManager: for asset validation and admission
    - Glass Box: AgentAction wrapping for all reviewer decisions
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.state import ResearchFellowshipState
from backend.mesh.library_manager import LibraryManager
from backend.schemas.diplomacy import (
    PeerReview,
    ReviewVerdict,
    SocraticExchange,
)
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "ritl-manager-v1"


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH NODE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def validate_submission(state: ResearchFellowshipState) -> dict[str, Any]:
    """Load and validate the submitted asset from LibraryManager."""
    if state.get("error"):
        return state

    asset_cid = state.get("asset_cid")
    if not asset_cid:
        return {**state, "error": "Missing asset_cid in submission."}

    lib = LibraryManager.get_instance()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                asset, action = pool.submit(
                    asyncio.run, lib.get_asset(asset_cid)
                ).result()
        else:
            asset, action = loop.run_until_complete(lib.get_asset(asset_cid))
    except KeyError:
        return {**state, "error": f"Asset not found: {asset_cid}"}

    asset_metadata = asset.model_dump(mode="json")

    return {
        **state,
        "asset_metadata": asset_metadata,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def assign_reviewers(state: ResearchFellowshipState) -> dict[str, Any]:
    """Assign reviewer agents to dimensions."""
    if state.get("error"):
        return state

    blind_mode = state.get("blind_mode", False)
    assignments = [
        {"reviewer_id": "rigor-reviewer-v1", "dimension": "Rigor",
         "display_id": "Reviewer-A" if blind_mode else "rigor-reviewer-v1"},
        {"reviewer_id": "novelty-reviewer-v1", "dimension": "Novelty",
         "display_id": "Reviewer-B" if blind_mode else "novelty-reviewer-v1"},
        {"reviewer_id": "ethics-reviewer-v1", "dimension": "Ethics",
         "display_id": "Reviewer-C" if blind_mode else "ethics-reviewer-v1"},
        {"reviewer_id": "reproducibility-reviewer-v1", "dimension": "Reproducibility",
         "display_id": "Reviewer-D" if blind_mode else "reproducibility-reviewer-v1"},
    ]

    action = AgentAction(
        agent_id=AGENT_ID,
        action="assign_reviewers",
        rationale=(
            f"Assigned 4 reviewer agents for asset {state.get('asset_cid')}. "
            f"Blind mode: {blind_mode}."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"assignments": assignments, "blind_mode": blind_mode},
    )

    return {
        **state,
        "reviewer_assignments": assignments,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def _review_node(
    dimension: str,
    reviewer_id: str,
    state: ResearchFellowshipState,
) -> dict[str, Any]:
    """Generic review node factory. Produces a PeerReview for the given dimension.

    STUB: Uses heuristic scoring. In production, this invokes the local
    LLM (OLMo) with a dimension-specific evaluation prompt.
    """
    if state.get("error"):
        return state

    asset_metadata = state.get("asset_metadata", {})
    title = asset_metadata.get("title", "Unknown")
    blind_mode = state.get("blind_mode", False)

    # STUB: Deterministic heuristic scoring based on dimension
    score_map = {
        "Rigor": 72,
        "Novelty": 65,
        "Ethics": 80,
        "Reproducibility": 68,
    }
    score = score_map.get(dimension, 70)

    # Determine verdict from score
    if score >= 75:
        verdict = ReviewVerdict.ACCEPT
    elif score >= 60:
        verdict = ReviewVerdict.MINOR_REVISIONS
    elif score >= 40:
        verdict = ReviewVerdict.MAJOR_REVISIONS
    else:
        verdict = ReviewVerdict.REJECT

    # Generate dimension-specific feedback
    strengths_map = {
        "Rigor": [f"Asset '{title}' demonstrates methodological clarity."],
        "Novelty": [f"Asset '{title}' addresses an underexplored topic."],
        "Ethics": [f"Asset '{title}' aligns with CCIN cooperative principles."],
        "Reproducibility": [f"Asset '{title}' provides sufficient context for reproduction."],
    }
    weaknesses_map = {
        "Rigor": ["Could benefit from additional empirical validation."],
        "Novelty": ["Significant overlap with existing commons resources noted."],
        "Ethics": ["Impact on care-work contributors should be explicitly addressed."],
        "Reproducibility": ["Dependency documentation could be more detailed."],
    }
    questions_map = {
        "Rigor": ["What empirical evidence supports the core claims?"],
        "Novelty": ["How does this differ from existing resources on this topic?"],
        "Ethics": ["Were care-work contributors consulted in the development?"],
        "Reproducibility": ["Can the methods be replicated with open-source tools only?"],
    }

    review = PeerReview(
        reviewer_id=reviewer_id,
        dimension=dimension,
        verdict=verdict,
        score=score,
        strengths=strengths_map.get(dimension, []),
        weaknesses=weaknesses_map.get(dimension, []),
        questions=questions_map.get(dimension, []),
        rationale=f"{dimension} assessment: score {score}/100 → {verdict.value}.",
        blind_mode=blind_mode,
    )

    action = AgentAction(
        agent_id=reviewer_id,
        action=f"peer_review_{dimension.lower()}",
        rationale=(
            f"{dimension} review for '{title}': score={score}, "
            f"verdict={verdict.value}. "
            f"Strengths: {len(review.strengths)}, "
            f"Weaknesses: {len(review.weaknesses)}, "
            f"Socratic questions: {len(review.questions)}."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "dimension": dimension,
            "score": score,
            "verdict": verdict.value,
            "question_count": len(review.questions),
        },
    )

    review.agent_action = action.model_dump()

    existing_reviews = list(state.get("reviews", []))
    existing_reviews.append(review.model_dump())

    return {
        **state,
        "reviews": existing_reviews,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def rigor_review(state: ResearchFellowshipState) -> dict[str, Any]:
    return _review_node("Rigor", "rigor-reviewer-v1", state)


def novelty_review(state: ResearchFellowshipState) -> dict[str, Any]:
    return _review_node("Novelty", "novelty-reviewer-v1", state)


def ethics_review(state: ResearchFellowshipState) -> dict[str, Any]:
    return _review_node("Ethics", "ethics-reviewer-v1", state)


def reproducibility_review(state: ResearchFellowshipState) -> dict[str, Any]:
    return _review_node("Reproducibility", "reproducibility-reviewer-v1", state)


def socratic_cross_examination(state: ResearchFellowshipState) -> dict[str, Any]:
    """Socratic Cross-Examination: reviewers challenge each other's weakest arguments.

    Each reviewer's questions (generated during their review) are directed at
    the other reviewers. Responses are generated and the full dialectic
    transcript is recorded.

    STUB: Generates synthetic cross-examination. In production, this invokes
    the LLM to produce targeted questions and responses.
    """
    if state.get("error"):
        return state

    reviews = state.get("reviews", [])
    blind_mode = state.get("blind_mode", False)
    exchanges: list[dict[str, Any]] = []
    round_number = 1

    for i, review in enumerate(reviews):
        questions = review.get("questions", [])
        reviewer_id = review.get("reviewer_id", f"reviewer-{i}")
        display_id = f"Reviewer-{chr(65 + i)}" if blind_mode else reviewer_id

        for question in questions:
            # Direct question to the next reviewer (round-robin)
            target_idx = (i + 1) % len(reviews)
            target_review = reviews[target_idx]
            target_id = target_review.get("reviewer_id", f"reviewer-{target_idx}")
            target_display = f"Reviewer-{chr(65 + target_idx)}" if blind_mode else target_id

            # STUB: Generate response based on target's dimension
            target_dimension = target_review.get("dimension", "General")
            response = (
                f"From {target_dimension} perspective: The concern is valid. "
                f"Our assessment accounts for this via the {target_dimension.lower()} "
                f"criteria, which scored {target_review.get('score', 0)}/100."
            )

            exchange = SocraticExchange(
                question=question,
                asked_by=display_id,
                response=response,
                responded_by=target_display,
                round_number=round_number,
            )
            exchanges.append(exchange.model_dump())
            round_number += 1

    action = AgentAction(
        agent_id=AGENT_ID,
        action="socratic_cross_examination",
        rationale=(
            f"Socratic Cross-Examination completed: {len(exchanges)} exchanges "
            f"across {len(reviews)} reviewers. Blind mode: {blind_mode}."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "exchange_count": len(exchanges),
            "reviewer_count": len(reviews),
            "blind_mode": blind_mode,
        },
    )

    return {
        **state,
        "socratic_exchanges": exchanges,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def evaluate_consensus(state: ResearchFellowshipState) -> dict[str, Any]:
    """Evaluate consensus across all reviews.

    Decision logic:
      - All ACCEPT → consensus = "accept"
      - Any REJECT → consensus = "reject"
      - Any MAJOR_REVISIONS → consensus = "major_revisions", requires HITL
      - Otherwise → consensus = "minor_revisions", requires HITL
    """
    if state.get("error"):
        return state

    reviews = state.get("reviews", [])
    verdicts = [r.get("verdict", "minor_revisions") for r in reviews]

    if all(v == "accept" for v in verdicts):
        consensus = "accept"
        requires_hitl = False
    elif any(v == "reject" for v in verdicts):
        consensus = "reject"
        requires_hitl = False
    elif any(v == "major_revisions" for v in verdicts):
        consensus = "major_revisions"
        requires_hitl = True
    else:
        consensus = "minor_revisions"
        requires_hitl = True

    action = AgentAction(
        agent_id=AGENT_ID,
        action="evaluate_research_consensus",
        rationale=(
            f"Peer review consensus: {consensus}. "
            f"Verdicts: {verdicts}. "
            f"HITL required: {requires_hitl}."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "consensus": consensus,
            "verdicts": verdicts,
            "requires_hitl": requires_hitl,
        },
    )

    return {
        **state,
        "review_consensus": consensus,
        "requires_human_token": requires_hitl,
        "escalation_signal": requires_hitl,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def human_review_research(state: ResearchFellowshipState) -> dict[str, Any]:
    """HITL breakpoint — graph pauses here for human researcher review.

    The researcher (or StewardshipCouncil) reviews the peer assessment,
    the Socratic transcript, and decides whether to admit, revise, or reject.
    """
    return {**state, "requires_human_token": False}


def finalize_admission(state: ResearchFellowshipState) -> dict[str, Any]:
    """Record the final admission decision.

    If consensus is 'accept' (or HITL approved), the asset is marked
    for promotion. Actual promotion to KnowledgeAsset happens via the
    IngestionEmbassy.admit() or directly via the router.
    """
    if state.get("error"):
        return state

    consensus = state.get("review_consensus", "reject")

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"finalize_admission:{consensus}",
        rationale=(
            f"RITL peer review finalized for asset {state.get('asset_cid')}: "
            f"consensus={consensus}. "
            f"Reviews: {len(state.get('reviews', []))}, "
            f"Socratic exchanges: {len(state.get('socratic_exchanges', []))}."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "asset_cid": state.get("asset_cid"),
            "consensus": consensus,
            "review_count": len(state.get("reviews", [])),
            "exchange_count": len(state.get("socratic_exchanges", [])),
        },
    )

    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def _route_after_consensus(state: ResearchFellowshipState) -> str:
    """Route based on consensus outcome."""
    if state.get("error"):
        return END

    consensus = state.get("review_consensus", "reject")

    if consensus == "accept":
        return "finalize_admission"
    elif consensus == "reject":
        return END
    else:
        # minor_revisions or major_revisions → HITL
        return "human_review_research"


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════════


def build_peer_review_graph() -> Any:
    """Build and compile the PeerReviewGraph StateGraph.

    Graph:
      validate_submission → assign_reviewers
        → rigor_review → novelty_review → ethics_review → reproducibility_review
        → socratic_cross_examination → evaluate_consensus
        → [conditional: finalize_admission | human_review_research | END]
        → finalize_admission → END
    """
    graph = StateGraph(ResearchFellowshipState)

    # Add nodes
    graph.add_node("validate_submission", validate_submission)
    graph.add_node("assign_reviewers", assign_reviewers)
    graph.add_node("rigor_review", rigor_review)
    graph.add_node("novelty_review", novelty_review)
    graph.add_node("ethics_review", ethics_review)
    graph.add_node("reproducibility_review", reproducibility_review)
    graph.add_node("socratic_cross_examination", socratic_cross_examination)
    graph.add_node("evaluate_consensus", evaluate_consensus)
    graph.add_node("human_review_research", human_review_research)
    graph.add_node("finalize_admission", finalize_admission)

    # Set entry point
    graph.set_entry_point("validate_submission")

    # Linear edges
    graph.add_edge("validate_submission", "assign_reviewers")
    graph.add_edge("assign_reviewers", "rigor_review")
    graph.add_edge("rigor_review", "novelty_review")
    graph.add_edge("novelty_review", "ethics_review")
    graph.add_edge("ethics_review", "reproducibility_review")
    graph.add_edge("reproducibility_review", "socratic_cross_examination")
    graph.add_edge("socratic_cross_examination", "evaluate_consensus")

    # Conditional: consensus outcome → next step
    graph.add_conditional_edges(
        "evaluate_consensus",
        _route_after_consensus,
        {
            "finalize_admission": "finalize_admission",
            "human_review_research": "human_review_research",
            END: END,
        },
    )

    # HITL → finalize
    graph.add_edge("human_review_research", "finalize_admission")

    # Finalize → END
    graph.add_edge("finalize_admission", END)

    # Compile with checkpointer and HITL breakpoint
    checkpointer = MemorySaver()
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review_research"],
    )


# Module-level compiled graph
peer_review_graph = build_peer_review_graph()
