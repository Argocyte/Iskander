"""
OutcomeAgent — Decision classification, outcome drafting, precedent storage.

Processes completed proposals: tallies votes, classifies the decision, drafts
an outcome statement, stores a precedent, and optionally triggers the TaskAgent.

Graph:
  tally_final_results → classify_decision → draft_outcome_statement
    → [conditional: human_approve_outcome if config requires | publish_outcome]
    → publish_outcome → store_precedent_data → broadcast_outcome
    → invoke_task_agent → END

Compiled with interrupt_before=["human_approve_outcome"].
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.core import load_prompt
from backend.agents.state import OutcomeState
from backend.config import settings
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)
AGENT_ID = "outcome-agent-v1"

# Process types that always pass regardless of tally values
INFORMATIONAL_TYPES = {"sense_check", "advice"}
POLL_TYPES = {"choose", "score", "allocate", "rank", "time_poll"}

# Keywords that indicate action items requiring task extraction
ACTION_KEYWORDS = {"should", "must", "will", "assign", "needs to"}


# ── Node implementations ───────────────────────────────────────────────────────

def tally_final_results(state: OutcomeState) -> dict[str, Any]:
    """Copy final_tally from state (already computed by caller) and log it."""
    tally = state.get("final_tally", {})
    action = AgentAction(
        agent_id=AGENT_ID,
        action="Tally final results",
        rationale="Recording the final vote tally for outcome classification",
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"tally": tally, "proposal_id": state.get("proposal_id")},
    )
    logger.info(
        "OutcomeAgent tally: proposal=%s tally=%s",
        state.get("proposal_id"),
        tally,
    )
    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def classify_decision(state: OutcomeState) -> dict[str, Any]:
    """Deterministically classify the decision based on process_type and tally.

    Classification rules:
    - Informational (sense_check, advice): always "passed"
    - Consent: "rejected" if block > 0, else "passed"
    - Consensus: "passed" if unanimous agree (no disagree/block), else "rejected"
    - Poll types (choose, score, allocate, rank, time_poll): always "passed"
    - Empty tally (total == 0): "no_quorum"
    """
    tally = state.get("final_tally", {})
    process_type = state.get("process_type", "")
    total = tally.get("total", 0)

    if total == 0:
        decision_type = "no_quorum"
    elif process_type in INFORMATIONAL_TYPES:
        decision_type = "passed"
    elif process_type in POLL_TYPES:
        decision_type = "passed"
    elif process_type == "consent":
        decision_type = "rejected" if tally.get("block", 0) > 0 else "passed"
    elif process_type == "consensus":
        # Unanimous: all votes are agrees with no disagrees or blocks
        agree = tally.get("agree", 0)
        disagree = tally.get("disagree", 0)
        block = tally.get("block", 0)
        if disagree > 0 or block > 0:
            decision_type = "rejected"
        else:
            decision_type = "passed"
    else:
        # Unknown process type — default to passed
        decision_type = "passed"

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Classify decision: {decision_type}",
        rationale=(
            f"Process '{process_type}' with tally {tally} yields '{decision_type}' "
            "per cooperative governance rules"
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "process_type": process_type,
            "tally": tally,
            "decision_type": decision_type,
        },
    )
    logger.info(
        "OutcomeAgent classify: process=%s decision=%s",
        process_type,
        decision_type,
    )
    return {
        **state,
        "decision_type": decision_type,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def draft_outcome_statement(state: OutcomeState) -> dict[str, Any]:
    """Draft outcome statement via LLM with deterministic fallback template."""
    decision_type = state.get("decision_type", "unknown")
    process_type = state.get("process_type", "unknown")
    tally = state.get("final_tally", {})
    proposal_id = state.get("proposal_id", "unknown")

    draft = None

    try:
        from langchain_ollama import ChatOllama
        prompt_template = load_prompt("prompt_outcome.txt")
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        user_message = (
            f"Proposal ID: {proposal_id}\n"
            f"Process type: {process_type}\n"
            f"Decision: {decision_type}\n"
            f"Tally: agree={tally.get('agree', 0)}, "
            f"disagree={tally.get('disagree', 0)}, "
            f"block={tally.get('block', 0)}, "
            f"abstain={tally.get('abstain', 0)}, "
            f"total={tally.get('total', 0)}\n\n"
            "Draft the official outcome statement for this proposal."
        )
        # Strip persona/precedent placeholders from template for agent use
        prompt = prompt_template.replace("{PERSONA_BLOCK}", "").replace(
            "{PRECEDENT_BLOCK}", "No prior precedents on record."
        )
        response = llm.invoke([
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message},
        ])
        raw = response.content.strip() if hasattr(response, "content") else str(response)
        if raw:
            draft = raw
    except Exception as exc:  # noqa: BLE001
        logger.warning("OutcomeAgent LLM call failed, using fallback: %s", exc)

    if not draft:
        # Deterministic fallback template
        draft = (
            f"Proposal {decision_type} via {process_type} process. "
            f"Tally: agree={tally.get('agree', 0)}, "
            f"disagree={tally.get('disagree', 0)}, "
            f"block={tally.get('block', 0)}."
        )

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Draft outcome statement",
        rationale="Produced outcome statement for cooperative governance record",
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={"proposal_id": proposal_id, "decision_type": decision_type},
    )
    return {
        **state,
        "draft_outcome": draft,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def human_approve_outcome(state: OutcomeState) -> dict[str, Any]:
    """No-op HITL breakpoint — execution pauses here for human countersignature."""
    action = AgentAction(
        agent_id=AGENT_ID,
        action="HITL breakpoint: human_approve_outcome",
        rationale="Config requires human approval before outcome is published",
        ethical_impact=EthicalImpactLevel.HIGH,
        payload={"proposal_id": state.get("proposal_id")},
    )
    return {
        **state,
        "requires_human_token": True,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def publish_outcome(state: OutcomeState) -> dict[str, Any]:
    """Package outcome for router INSERT. Logs action."""
    action = AgentAction(
        agent_id=AGENT_ID,
        action="Publish outcome",
        rationale="Outcome classified and approved; packaging for router persistence",
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "proposal_id": state.get("proposal_id"),
            "decision_type": state.get("decision_type"),
        },
    )
    logger.info(
        "OutcomeAgent publish: proposal=%s decision=%s",
        state.get("proposal_id"),
        state.get("decision_type"),
    )
    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def store_precedent_data(state: OutcomeState) -> dict[str, Any]:
    """Prepare precedent_data dict for router to persist as governance precedent."""
    tally = state.get("final_tally", {})
    decision_type = state.get("decision_type")
    precedent_data = {
        "source_agent": AGENT_ID,
        "decision_type": decision_type,
        "original_text": state.get("draft_outcome"),
        "vote_result": decision_type,
        "metadata": {
            "proposal_id": state.get("proposal_id"),
            "tally": tally,
        },
    }
    action = AgentAction(
        agent_id=AGENT_ID,
        action="Store precedent data",
        rationale="Packaging outcome as democratic precedent for governance archive",
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload=precedent_data,
    )
    return {
        **state,
        "precedent_data": precedent_data,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def broadcast_outcome(state: OutcomeState) -> dict[str, Any]:
    """Format WebSocket event for outcome_stated broadcast."""
    event = {
        "type": "outcome_stated",
        "proposal_id": state.get("proposal_id"),
        "thread_id": state.get("thread_id"),
        "decision_type": state.get("decision_type"),
        "draft_outcome": state.get("draft_outcome"),
    }
    action = AgentAction(
        agent_id=AGENT_ID,
        action="Broadcast outcome_stated event",
        rationale="Notifying members of the finalised outcome via WebSocket",
        ethical_impact=EthicalImpactLevel.LOW,
        payload=event,
    )
    logger.info("OutcomeAgent broadcast: %s", event)
    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


def invoke_task_agent(state: OutcomeState) -> dict[str, Any]:
    """Scan draft_outcome for action keywords; set should_extract_tasks if found."""
    draft = state.get("draft_outcome") or ""
    draft_lower = draft.lower()
    found = any(kw in draft_lower for kw in ACTION_KEYWORDS)

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Scan for action keywords: should_extract_tasks={found}",
        rationale=(
            "Checking outcome statement for action verbs that indicate "
            "concrete tasks requiring extraction"
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"keywords_found": found, "keywords_checked": sorted(ACTION_KEYWORDS)},
    )
    return {
        **state,
        "should_extract_tasks": found,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Conditional routing ────────────────────────────────────────────────────────

def _route_after_draft(state: OutcomeState) -> str:
    """Route to HITL breakpoint or directly to publish based on config."""
    if settings.deliberation_outcome_require_approval:
        return "human_approve_outcome"
    return "publish_outcome"


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_outcome_graph():
    """Compile the OutcomeAgent LangGraph."""
    g = StateGraph(OutcomeState)

    g.add_node("tally_final_results", tally_final_results)
    g.add_node("classify_decision", classify_decision)
    g.add_node("draft_outcome_statement", draft_outcome_statement)
    g.add_node("human_approve_outcome", human_approve_outcome)
    g.add_node("publish_outcome", publish_outcome)
    g.add_node("store_precedent_data", store_precedent_data)
    g.add_node("broadcast_outcome", broadcast_outcome)
    g.add_node("invoke_task_agent", invoke_task_agent)

    g.set_entry_point("tally_final_results")
    g.add_edge("tally_final_results", "classify_decision")
    g.add_edge("classify_decision", "draft_outcome_statement")
    g.add_conditional_edges(
        "draft_outcome_statement",
        _route_after_draft,
        {
            "human_approve_outcome": "human_approve_outcome",
            "publish_outcome": "publish_outcome",
        },
    )
    g.add_edge("human_approve_outcome", "publish_outcome")
    g.add_edge("publish_outcome", "store_precedent_data")
    g.add_edge("store_precedent_data", "broadcast_outcome")
    g.add_edge("broadcast_outcome", "invoke_task_agent")
    g.add_edge("invoke_task_agent", END)

    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_approve_outcome"],
    )


outcome_graph = build_outcome_graph()
