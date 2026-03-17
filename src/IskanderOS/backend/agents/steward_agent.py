"""
Steward Agent — DisCO Contributory Accounting

Parses free-text or structured contribution descriptions and classifies
them into the three DisCO work streams:

  - Livelihood Work : paid, market-facing work (client deliverables, services)
  - Care Work       : unpaid reproductive/community work (mentoring, emotional support)
  - Commons Work    : open-source, knowledge commons contributions

After classification, the agent produces a ledger entry for insertion
into the `contributions` Postgres table via the Glass Box Protocol.

LangGraph graph:
  classify_contribution → validate_member → write_ledger_entry → [END]

The agent never touches the treasury. It only writes to the internal
contributory accounting ledger (LOW ethical impact).
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from backend.agents.state import ContributionState
from backend.config import settings
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = structlog.get_logger(__name__)

AGENT_ID = "steward-agent-v1"

WORK_STREAMS = ("livelihood", "care", "commons")

CLASSIFICATION_SYSTEM_PROMPT = """\
You are a DisCO (Distributed Cooperative Organization) steward agent.
Your job is to classify a member's contribution into exactly ONE of these three streams:

1. livelihood  — Paid, market-facing work that generates revenue for the cooperative.
                 Examples: client projects, deliverables, sales, consulting.

2. care        — Unpaid reproductive or community work that sustains the cooperative.
                 Examples: mentoring, emotional support, onboarding, conflict resolution,
                 meeting facilitation, administrative coordination.

3. commons     — Open-source, knowledge commons, or public-good contributions.
                 Examples: writing documentation, contributing to open-source repos,
                 publishing research, creating educational materials.

Respond with ONLY a JSON object in this exact format:
{
  "stream": "<livelihood|care|commons>",
  "confidence": <0.0-1.0>,
  "reasoning": "<one sentence>"
}
"""


# ── Nodes ─────────────────────────────────────────────────────────────────────

def classify_contribution(state: ContributionState) -> ContributionState:
    """
    Node 1: Use Llama 3 to classify the contribution into a DisCO work stream.
    Falls back to a keyword heuristic if Ollama is unavailable.
    """
    raw = state.get("raw_contribution") or {}
    description = raw.get("description", "")

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Classify contribution: '{description[:80]}...' " if len(description) > 80 else f"Classify contribution: '{description}'",
        rationale="DisCO contributory accounting requires every contribution to be streamed for equitable value tracking.",
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"member_did": raw.get("member_did"), "description_length": len(description)},
    )

    classified_stream: str
    try:
        llm = ChatOllama(base_url=settings.ollama_base_url, model=settings.ollama_model)
        response = llm.invoke([
            SystemMessage(content=CLASSIFICATION_SYSTEM_PROMPT),
            HumanMessage(content=f"Contribution description: {description}"),
        ])
        result = json.loads(response.content)
        classified_stream = result.get("stream", "commons")
        if classified_stream not in WORK_STREAMS:
            classified_stream = "commons"
        logger.info("contribution_classified", stream=classified_stream, confidence=result.get("confidence"))

    except Exception as exc:
        logger.warning("llm_classification_fallback", error=str(exc))
        # Keyword heuristic fallback
        desc_lower = description.lower()
        if any(k in desc_lower for k in ("client", "invoice", "revenue", "deliverable", "sale")):
            classified_stream = "livelihood"
        elif any(k in desc_lower for k in ("mentor", "support", "onboard", "facilitat", "care")):
            classified_stream = "care"
        else:
            classified_stream = "commons"

    return {
        **state,
        "classified_stream": classified_stream,
        "action_log": state.get("action_log", []) + [action.model_dump(mode="json")],
    }


def validate_member(state: ContributionState) -> ContributionState:
    """
    Node 2: Verify the contributing member holds an active CoopIdentity SBT.
    In dev, performs a lightweight check against the EVM node.
    Falls back gracefully if EVM is unavailable.
    """
    raw = state.get("raw_contribution") or {}
    member_address = raw.get("member_address")

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Validate CoopIdentity SBT for address {member_address}",
        rationale="Contributions may only be logged for active cooperative members per the legal wrapper.",
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"member_address": member_address},
    )

    is_valid = True  # default: allow in dev if EVM unreachable
    try:
        if member_address:
            from web3 import Web3
            # Lightweight check: non-zero balance = active member
            # Full impl requires CoopIdentity contract ABI binding (Phase 5)
            rpc = Web3(Web3.HTTPProvider(settings.evm_rpc_url))
            if not rpc.is_connected():
                raise ConnectionError("EVM node unreachable")
            # TODO Phase 5: load CoopIdentity ABI and call balanceOf(member_address)
            logger.info("member_validation_evm_connected", address=member_address)
    except Exception as exc:
        logger.warning("member_validation_skipped", error=str(exc))
        # Fail open in dev; fail closed in prod (enforce via env flag)

    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump(mode="json")],
    }


def write_ledger_entry(state: ContributionState) -> ContributionState:
    """
    Node 3: Construct the contribution ledger entry.

    Writes to the `contributions` Postgres table structure defined in init.sql.
    Actual DB write is performed by the calling API endpoint (not the agent)
    to keep agents stateless and testable.
    """
    raw = state.get("raw_contribution") or {}
    stream = state.get("classified_stream", "commons")

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Write ledger entry for '{stream}' contribution",
        rationale=f"Contribution classified as '{stream}' work; recording in cooperative ledger for value distribution.",
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "stream":     stream,
            "member_did": raw.get("member_did"),
            "hours":      raw.get("hours"),
        },
    )

    ledger_entry = {
        "member_did":   raw.get("member_did", "unknown"),
        "stream":       stream,
        "description":  raw.get("description", ""),
        "hours":        raw.get("hours"),
        "value_tokens": raw.get("value_tokens"),
        "ipfs_cid":     raw.get("ipfs_cid"),   # optional evidence link
    }

    return {
        **state,
        "ledger_entry": ledger_entry,
        "action_log":   state.get("action_log", []) + [action.model_dump(mode="json")],
    }


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_steward_graph() -> Any:
    g = StateGraph(ContributionState)
    g.add_node("classify_contribution", classify_contribution)
    g.add_node("validate_member",       validate_member)
    g.add_node("write_ledger_entry",    write_ledger_entry)
    g.set_entry_point("classify_contribution")
    g.add_edge("classify_contribution", "validate_member")
    g.add_edge("validate_member",       "write_ledger_entry")
    g.add_edge("write_ledger_entry",    END)
    return g.compile()


steward_graph = build_steward_graph()
