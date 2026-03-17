"""
curator_network.py — Iskander Knowledge Commons Curator Network (IKC).

Three specialized Curator agents (Efficiency, Ethics, Resilience) evaluate
proposed status changes to KnowledgeAssets through a dialectic consensus
process. Unanimous consent is required; mixed votes escalate to the
StewardshipCouncil via HITL.

Graph:
  validate_proposal → check_downstream_impact
    → [conditional: reject if active deps exist for tombstone/legacy]
    → check_break_glass
    → [conditional: pause if break-glass active]
    → efficiency_curator_vote → ethics_curator_vote
    → resilience_curator_vote → evaluate_consensus
    → [conditional:
         unanimous_approve → apply_status_change → END
         unanimous_reject  → END
         mixed             → human_review_curation (HITL)
                           → apply_status_change → END]

DESIGN CONSTRAINTS:
  - Tombstone-Only: NEVER delete CIDs. Only write StatusTag metadata.
  - Glass Box Protocol: every curator vote is wrapped in AgentAction.
  - Break-Glass: StewardshipCouncil can halt all curation immediately.
  - Dependency Safety: assets with active dependents cannot be tombstoned.
  - HITL Escalation: non-unanimous votes MUST escalate to human review.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.state import CuratorDebateState
from backend.config import settings
from backend.mesh.library_manager import LibraryManager
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel
from backend.schemas.knowledge import KnowledgeAssetStatus

logger = logging.getLogger(__name__)

AGENT_ID_NETWORK    = "curator-network-v1"
AGENT_ID_EFFICIENCY = "efficiency-curator-v1"
AGENT_ID_ETHICS     = "ethics-curator-v1"
AGENT_ID_RESILIENCE = "resilience-curator-v1"


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH NODES
# ═══════════════════════════════════════════════════════════════════════════════


# ── Node 1: Validate Proposal ─────────────────────────────────────────────────

def validate_proposal(state: CuratorDebateState) -> dict[str, Any]:
    """Load asset from LibraryManager, verify CID exists and transition valid."""
    if state.get("error"):
        return state

    asset_cid = state.get("asset_cid")
    proposed_status_str = state.get("proposed_status")

    if not asset_cid or not proposed_status_str:
        return {
            **state,
            "error": "Missing asset_cid or proposed_status in state.",
        }

    try:
        proposed_status = KnowledgeAssetStatus(proposed_status_str)
    except ValueError:
        return {
            **state,
            "error": f"Invalid proposed_status: {proposed_status_str}",
        }

    lib = LibraryManager.get_instance()
    try:
        import asyncio
        asset, _action = asyncio.get_event_loop().run_until_complete(
            lib.get_asset(asset_cid)
        )
    except KeyError:
        return {**state, "error": f"Asset not found: {asset_cid}"}

    asset_dict = asset.model_dump(mode="json")

    # Check transition validity
    from backend.mesh.library_manager import VALID_TRANSITIONS
    allowed = VALID_TRANSITIONS.get(asset.status, set())
    if proposed_status not in allowed:
        return {
            **state,
            "error": (
                f"Invalid transition: {asset.status.value} → "
                f"{proposed_status.value}"
            ),
        }

    action = AgentAction(
        agent_id=AGENT_ID_NETWORK,
        action="validate_proposal",
        rationale=(
            f"Validated curation proposal for asset {asset_cid}: "
            f"transition {asset.status.value} → {proposed_status.value} "
            f"is permitted. Asset title: '{asset.title}'."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={
            "asset_cid": asset_cid,
            "current_status": asset.status.value,
            "proposed_status": proposed_status.value,
            "title": asset.title,
        },
    )

    return {
        **state,
        "asset_metadata": asset_dict,
        "rationale_log": state.get("rationale_log", []) + [
            f"Proposal validated: {asset.status.value} → {proposed_status.value}"
        ],
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 2: Check Downstream Impact ───────────────────────────────────────────

def check_downstream_impact(state: CuratorDebateState) -> dict[str, Any]:
    """Graph traversal: check if any active assets depend on this CID.

    If dependents exist AND proposed status is Tombstoned or Legacy,
    the proposal MUST be rejected.
    """
    if state.get("error"):
        return state

    asset_cid = state.get("asset_cid", "")
    proposed = state.get("proposed_status", "")

    lib = LibraryManager.get_instance()
    import asyncio
    deps, dep_action = asyncio.get_event_loop().run_until_complete(
        lib.check_downstream_impact(asset_cid)
    )

    # Only block for destructive transitions
    destructive = proposed in (
        KnowledgeAssetStatus.TOMBSTONED.value,
        KnowledgeAssetStatus.LEGACY.value,
    )
    check_passed = not (destructive and len(deps) > 0)

    consensus = state.get("consensus_status", "in_progress")
    rationale_entry = (
        f"Downstream impact: {len(deps)} active dependent(s). "
        f"Check {'passed' if check_passed else 'FAILED — deps block this transition'}."
    )

    if not check_passed:
        consensus = "rejected_downstream_deps"

    action = AgentAction(
        agent_id=AGENT_ID_NETWORK,
        action="check_downstream_impact",
        rationale=(
            f"Checked downstream impact for {asset_cid}. "
            f"Found {len(deps)} active dependent(s): {deps}. "
            f"Proposed status: {proposed}. "
            f"{'BLOCKED: active dependents prevent destructive transition.' if not check_passed else 'No blocking dependencies.'}"
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={
            "asset_cid": asset_cid,
            "dependents": deps,
            "check_passed": check_passed,
        },
    )

    return {
        **state,
        "downstream_deps": deps,
        "dependency_check_passed": check_passed,
        "consensus_status": consensus,
        "rationale_log": state.get("rationale_log", []) + [rationale_entry],
        "action_log": state.get("action_log", []) + [dep_action.model_dump(), action.model_dump()],
    }


# ── Node 3: Check Break-Glass ─────────────────────────────────────────────────

def check_break_glass(state: CuratorDebateState) -> dict[str, Any]:
    """Read global Break-Glass flag. If active, pause the debate."""
    if state.get("error"):
        return state

    lib = LibraryManager.get_instance()
    is_active = lib.break_glass_active

    consensus = state.get("consensus_status", "in_progress")
    if is_active:
        consensus = "paused"

    action = AgentAction(
        agent_id=AGENT_ID_NETWORK,
        action="check_break_glass",
        rationale=(
            f"Break-Glass status: {'ACTIVE — debate paused' if is_active else 'inactive — proceeding'}."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"break_glass_active": is_active},
    )

    return {
        **state,
        "break_glass_active": is_active,
        "consensus_status": consensus,
        "rationale_log": state.get("rationale_log", []) + [
            f"Break-Glass: {'ACTIVE — paused' if is_active else 'inactive'}"
        ],
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: Efficiency Curator Vote ───────────────────────────────────────────

def efficiency_curator_vote(state: CuratorDebateState) -> dict[str, Any]:
    """Evaluate: storage cost, redundancy ratio, access frequency, version bloat.

    STUB: Heuristic scoring. Production: LLM-based assessment using
    asset metadata and mesh telemetry.
    """
    if state.get("error"):
        return state

    asset = state.get("asset_metadata", {})
    proposed = state.get("proposed_status", "")

    # Heuristic: Tombstoning saves storage → approve. Legacy is neutral.
    # DeepFreeze costs more (permanent pin) → slight disapproval.
    score_map = {
        "Tombstoned": 75,
        "Legacy": 60,
        "DeepFreeze": 40,
        "Active": 50,
    }
    score = score_map.get(proposed, 50)

    # Adjust based on dependency count (more deps = less efficient to change)
    dep_count = len(asset.get("dependency_manifest", []))
    if dep_count > 5:
        score = max(0, score - 10)

    vote_value = "approve" if score >= 50 else "reject"
    rationale_text = (
        f"Efficiency assessment: score={score}/100. "
        f"Proposed status '{proposed}' evaluated for storage cost and "
        f"redundancy impact. Dependency count: {dep_count}."
    )

    action = AgentAction(
        agent_id=AGENT_ID_EFFICIENCY,
        action=f"curator_vote:Efficiency:{vote_value}",
        rationale=rationale_text,
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "dimension": "Efficiency",
            "vote": vote_value,
            "score": score,
            "asset_cid": state.get("asset_cid"),
        },
    )

    vote = {
        "curator_id": AGENT_ID_EFFICIENCY,
        "dimension": "Efficiency",
        "vote": vote_value,
        "score": score,
        "rationale": rationale_text,
        "agent_action": action.model_dump(),
    }

    return {
        **state,
        "votes": state.get("votes", []) + [vote],
        "rationale_log": state.get("rationale_log", []) + [
            f"Efficiency: {vote_value} (score={score})"
        ],
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 5: Ethics Curator Vote ───────────────────────────────────────────────

def ethics_curator_vote(state: CuratorDebateState) -> dict[str, Any]:
    """Evaluate: author consent, community impact, CCIN alignment, care-work.

    STUB: Heuristic scoring. Production: LLM cross-checks rationale against
    CCIN principles via ccin_verifier.
    """
    if state.get("error"):
        return state

    proposed = state.get("proposed_status", "")
    proposer_rationale = state.get("proposer_rationale", "") or ""

    # Heuristic: Tombstoning requires strong ethical justification.
    # DeepFreeze preserves content (ethical). Legacy is neutral.
    score = 50
    if proposed == "Tombstoned":
        # Tombstoning is ethically sensitive — requires explicit rationale
        if len(proposer_rationale) > 50:
            score = 65  # Rationale provided → lean approve
        else:
            score = 35  # Weak rationale → lean reject
    elif proposed == "DeepFreeze":
        score = 70  # Preservation is ethically positive
    elif proposed == "Legacy":
        score = 60  # Mild deprecation, acceptable

    vote_value = "approve" if score >= 50 else "reject"
    rationale_text = (
        f"Ethics assessment: score={score}/100. "
        f"Evaluated CCIN principle alignment for '{proposed}' transition. "
        f"Proposer rationale length: {len(proposer_rationale)} chars. "
        f"{'Adequate justification provided.' if score >= 50 else 'Insufficient ethical justification.'}"
    )

    action = AgentAction(
        agent_id=AGENT_ID_ETHICS,
        action=f"curator_vote:Ethics:{vote_value}",
        rationale=rationale_text,
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "dimension": "Ethics",
            "vote": vote_value,
            "score": score,
            "asset_cid": state.get("asset_cid"),
        },
    )

    vote = {
        "curator_id": AGENT_ID_ETHICS,
        "dimension": "Ethics",
        "vote": vote_value,
        "score": score,
        "rationale": rationale_text,
        "agent_action": action.model_dump(),
    }

    return {
        **state,
        "votes": state.get("votes", []) + [vote],
        "rationale_log": state.get("rationale_log", []) + [
            f"Ethics: {vote_value} (score={score})"
        ],
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 6: Resilience Curator Vote ───────────────────────────────────────────

def resilience_curator_vote(state: CuratorDebateState) -> dict[str, Any]:
    """Evaluate: replica count, geographic diversity, recovery path, dep depth.

    STUB: Heuristic scoring. Production: queries mesh telemetry for
    actual replica counts and peer geo-diversity.
    """
    if state.get("error"):
        return state

    proposed = state.get("proposed_status", "")
    deps = state.get("downstream_deps", [])

    # Heuristic: Tombstoning reduces resilience if others reference it.
    # DeepFreeze is maximally resilient (permanent). Legacy is neutral.
    score = 50
    if proposed == "Tombstoned":
        score = 55 if len(deps) == 0 else 30
    elif proposed == "DeepFreeze":
        score = 80  # Maximum preservation
    elif proposed == "Legacy":
        score = 55

    vote_value = "approve" if score >= 50 else "reject"
    rationale_text = (
        f"Resilience assessment: score={score}/100. "
        f"Evaluated recovery path and replica impact for '{proposed}' "
        f"transition. Downstream dependents: {len(deps)}. "
        f"{'System resilience maintained.' if score >= 50 else 'Risk to system resilience.'}"
    )

    action = AgentAction(
        agent_id=AGENT_ID_RESILIENCE,
        action=f"curator_vote:Resilience:{vote_value}",
        rationale=rationale_text,
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "dimension": "Resilience",
            "vote": vote_value,
            "score": score,
            "asset_cid": state.get("asset_cid"),
        },
    )

    vote = {
        "curator_id": AGENT_ID_RESILIENCE,
        "dimension": "Resilience",
        "vote": vote_value,
        "score": score,
        "rationale": rationale_text,
        "agent_action": action.model_dump(),
    }

    return {
        **state,
        "votes": state.get("votes", []) + [vote],
        "rationale_log": state.get("rationale_log", []) + [
            f"Resilience: {vote_value} (score={score})"
        ],
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 7: Evaluate Consensus ────────────────────────────────────────────────

def evaluate_consensus(state: CuratorDebateState) -> dict[str, Any]:
    """Determine consensus from 3 curator votes.

    Unanimous approve → apply. Unanimous reject → end.
    Mixed → escalate to StewardshipCouncil HITL.
    """
    if state.get("error"):
        return state

    votes = state.get("votes", [])
    vote_values = [v.get("vote") for v in votes]

    all_approve = all(v == "approve" for v in vote_values)
    all_reject = all(v == "reject" for v in vote_values)

    if all_approve:
        consensus = "unanimous_approve"
        escalate = False
        hitl = False
    elif all_reject:
        consensus = "unanimous_reject"
        escalate = False
        hitl = False
    else:
        consensus = "escalated"
        escalate = True
        hitl = True

    avg_score = (
        sum(v.get("score", 0) for v in votes) / len(votes)
        if votes else 0
    )

    action = AgentAction(
        agent_id=AGENT_ID_NETWORK,
        action=f"evaluate_consensus:{consensus}",
        rationale=(
            f"Consensus evaluation: {consensus}. "
            f"Votes: {vote_values}. Average score: {avg_score:.1f}/100. "
            f"{'Escalating to StewardshipCouncil for human review.' if escalate else 'Consensus reached autonomously.'}"
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "consensus_status": consensus,
            "vote_summary": vote_values,
            "average_score": avg_score,
            "escalation_signal": escalate,
        },
    )

    return {
        **state,
        "consensus_status": consensus,
        "escalation_signal": escalate,
        "requires_human_token": hitl,
        "rationale_log": state.get("rationale_log", []) + [
            f"Consensus: {consensus} (avg_score={avg_score:.1f})"
        ],
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 8: Human Review (HITL no-op) ─────────────────────────────────────────

def human_review_curation(state: CuratorDebateState) -> dict[str, Any]:
    """HITL no-op node. Graph pauses via interrupt_before when
    requires_human_token is True. Router resumes after council approval."""
    return {**state, "requires_human_token": False}


# ── Node 9: Apply Status Change ───────────────────────────────────────────────

def apply_status_change(state: CuratorDebateState) -> dict[str, Any]:
    """Call LibraryManager.update_status(). Pin StatusTag to IPFS.

    TOMBSTONE-ONLY: This node NEVER deletes a CID. It only writes
    metadata via LibraryManager.update_status().
    """
    if state.get("error"):
        return state

    asset_cid = state.get("asset_cid", "")
    proposed = state.get("proposed_status", "")
    proposer_rationale = state.get("proposer_rationale", "") or "Curator consensus"

    try:
        new_status = KnowledgeAssetStatus(proposed)
    except ValueError:
        return {**state, "error": f"Invalid status: {proposed}"}

    lib = LibraryManager.get_instance()
    try:
        import asyncio
        tag, status_action = asyncio.get_event_loop().run_until_complete(
            lib.update_status(
                cid=asset_cid,
                new_status=new_status,
                changed_by=AGENT_ID_NETWORK,
                rationale=proposer_rationale,
            )
        )
    except ValueError as exc:
        return {**state, "error": str(exc)}

    action = AgentAction(
        agent_id=AGENT_ID_NETWORK,
        action=f"apply_status_change:{proposed}",
        rationale=(
            f"Applied status change for asset {asset_cid}: → {proposed}. "
            f"StatusTag pinned at CID {tag.asset_cid}. "
            f"Original content CID preserved (tombstone-only invariant)."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "asset_cid": asset_cid,
            "new_status": proposed,
            "metadata_cid": tag.asset_cid,
        },
    )

    return {
        **state,
        "rationale_log": state.get("rationale_log", []) + [
            f"Status change applied: → {proposed}"
        ],
        "action_log": state.get("action_log", []) + [
            status_action.model_dump(),
            action.model_dump(),
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _route_after_dependency_check(state: CuratorDebateState) -> str:
    """Route after dependency check: reject if deps block transition."""
    if state.get("error"):
        return END
    if not state.get("dependency_check_passed", True):
        return END  # rejected_downstream_deps
    return "check_break_glass"


def _route_after_break_glass(state: CuratorDebateState) -> str:
    """Route after break-glass check: pause if active."""
    if state.get("error"):
        return END
    if state.get("break_glass_active"):
        return END  # paused
    return "efficiency_curator_vote"


def _route_after_consensus(state: CuratorDebateState) -> str:
    """Route after consensus evaluation."""
    if state.get("error"):
        return END
    cs = state.get("consensus_status")
    if cs == "unanimous_approve":
        return "apply_status_change"
    if cs == "unanimous_reject":
        return END
    # Mixed → escalate to HITL
    return "human_review_curation"


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH ASSEMBLY
# ═══════════════════════════════════════════════════════════════════════════════

def build_curator_network_graph() -> Any:
    """Build and compile the CuratorDebate StateGraph."""
    g = StateGraph(CuratorDebateState)

    # Add nodes
    g.add_node("validate_proposal", validate_proposal)
    g.add_node("check_downstream_impact", check_downstream_impact)
    g.add_node("check_break_glass", check_break_glass)
    g.add_node("efficiency_curator_vote", efficiency_curator_vote)
    g.add_node("ethics_curator_vote", ethics_curator_vote)
    g.add_node("resilience_curator_vote", resilience_curator_vote)
    g.add_node("evaluate_consensus", evaluate_consensus)
    g.add_node("human_review_curation", human_review_curation)
    g.add_node("apply_status_change", apply_status_change)

    # Entry point
    g.set_entry_point("validate_proposal")

    # Edges
    g.add_edge("validate_proposal", "check_downstream_impact")

    g.add_conditional_edges(
        "check_downstream_impact",
        _route_after_dependency_check,
        {"check_break_glass": "check_break_glass", END: END},
    )

    g.add_conditional_edges(
        "check_break_glass",
        _route_after_break_glass,
        {"efficiency_curator_vote": "efficiency_curator_vote", END: END},
    )

    g.add_edge("efficiency_curator_vote", "ethics_curator_vote")
    g.add_edge("ethics_curator_vote", "resilience_curator_vote")
    g.add_edge("resilience_curator_vote", "evaluate_consensus")

    g.add_conditional_edges(
        "evaluate_consensus",
        _route_after_consensus,
        {
            "apply_status_change": "apply_status_change",
            "human_review_curation": "human_review_curation",
            END: END,
        },
    )

    g.add_edge("human_review_curation", "apply_status_change")
    g.add_edge("apply_status_change", END)

    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_review_curation"],
    )


# Module-level compiled graph
curator_network_graph = build_curator_network_graph()
