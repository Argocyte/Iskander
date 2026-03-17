"""
Procurement Agent — Cooperative-first supply chain sourcing with Valueflows/REA.

Graph: parse_purchase_request → search_cooperative_vendors
       → rank_and_select_vendor → prepare_order → END
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph

from backend.agents.core import load_prompt
from backend.agents.core.glass_box_parser import GlassBoxParser
from backend.agents.core.persona_generator import build_agent_prompt
from backend.agents.state import ProcurementState
from backend.config import settings
from backend.routers.power import agents_are_paused
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "procurement-agent-v1"

_role_prompt = load_prompt("prompt_procurement.txt")
_parser = GlassBoxParser()

# ── Vendor priority tiers ─────────────────────────────────────────────────────

TIER_COOPERATIVE = 1
TIER_SOCIAL_ENTERPRISE = 2
TIER_LOCAL_BUSINESS = 3
TIER_CONVENTIONAL = 4


# ── Node 1: Parse purchase request ───────────────────────────────────────────

_PARSE_PROMPT = (
    "Parse the following purchase request into structured fields.  "
    "Respond with ONLY a JSON object:\n"
    '{"item": "...", "quantity": N, "unit": "...", '
    '"budget_max": N, "currency": "...", "urgency": "low"|"medium"|"high", '
    '"notes": "..."}\n\n'
    "REQUEST:\n{request_text}"
)


def parse_purchase_request(state: ProcurementState) -> dict[str, Any]:
    """LLM-powered parsing of natural-language purchase requests."""
    if agents_are_paused():
        return {**state, "error": "Agents paused (low power mode)."}

    req = state.get("purchase_request", {}) or {}
    request_text = req.get("description", "")

    if not request_text.strip():
        return {**state, "error": "Empty purchase request."}

    try:
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        resp = llm.invoke(_PARSE_PROMPT.format(request_text=request_text[:3000]))
        parsed = _parse_json_obj(resp.content)
        # Merge parsed fields back into the request.
        req = {**req, **parsed}
    except Exception as exc:
        logger.warning("Purchase parsing LLM failed: %s", exc)
        # Proceed with raw request fields.

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Parse purchase request",
        rationale="Structured procurement data enables Valueflows/REA compliance.",
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"item": req.get("item", request_text[:100])},
    )

    return {
        **state,
        "purchase_request": req,
        "action_log": state.get("action_log", []) + [action.model_dump()],
        "error": None,
    }


# ── Node 2: Search cooperative vendors ────────────────────────────────────────

# Stub vendor registry — in production, this queries federated cooperative
# directories via ActivityPub and/or a local SQL vendor table.
_STUB_COOPERATIVE_VENDORS: list[dict[str, Any]] = [
    {
        "name": "Solidarity Tech Coop",
        "did": "did:iskander:coop:solidarity-tech",
        "tier": TIER_COOPERATIVE,
        "capabilities": ["hardware", "electronics", "networking"],
    },
    {
        "name": "Commons Provisions Coop",
        "did": "did:iskander:coop:commons-provisions",
        "tier": TIER_COOPERATIVE,
        "capabilities": ["office supplies", "furniture", "provisions"],
    },
    {
        "name": "Green Workers B-Corp",
        "did": "did:iskander:bcorp:green-workers",
        "tier": TIER_SOCIAL_ENTERPRISE,
        "capabilities": ["cleaning", "maintenance", "sustainability"],
    },
]


def search_cooperative_vendors(state: ProcurementState) -> dict[str, Any]:
    """Search for vendors — cooperative DIDs first, then fallback tiers.

    TODO: Query ActivityPub federation for peer cooperative Actor profiles.
    Currently uses a stub registry for development.
    """
    req = state.get("purchase_request", {}) or {}
    item = req.get("item", "").lower()

    # Simple capability matching against stub registry.
    candidates = []
    for vendor in _STUB_COOPERATIVE_VENDORS:
        if any(cap in item or item in cap for cap in vendor["capabilities"]):
            candidates.append(vendor)

    # If no cooperative matches, add a conventional vendor placeholder.
    if not candidates:
        candidates.append({
            "name": "(conventional vendor — search required)",
            "did": None,
            "tier": TIER_CONVENTIONAL,
            "capabilities": [item],
        })

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Vendor search: {len(candidates)} candidates found",
        rationale=(
            "CCIN Principle 6 (Cooperation Among Cooperatives) — "
            "cooperative vendors searched first."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"candidate_count": len(candidates), "tiers": [c["tier"] for c in candidates]},
    )

    return {
        **state,
        "vendor_candidates": candidates,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 3: Rank and select vendor ───────────────────────────────────────────


def rank_and_select_vendor(state: ProcurementState) -> dict[str, Any]:
    """Rank candidates by cooperative alignment (tier), then select best."""
    candidates = state.get("vendor_candidates", [])
    if not candidates:
        return {
            **state,
            "selected_vendor": None,
            "error": "No vendor candidates available.",
        }

    # Sort by tier (lower = more aligned).
    ranked = sorted(candidates, key=lambda v: v.get("tier", TIER_CONVENTIONAL))
    selected = ranked[0]

    is_conventional = selected.get("tier", TIER_CONVENTIONAL) == TIER_CONVENTIONAL
    impact = EthicalImpactLevel.HIGH if is_conventional else EthicalImpactLevel.MEDIUM

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Selected vendor: {selected.get('name', 'unknown')} (tier {selected.get('tier')})",
        rationale=(
            f"Vendor selected from {len(ranked)} candidates.  "
            f"{'CONVENTIONAL vendor — all cooperative alternatives exhausted.  Requires human approval.' if is_conventional else 'Cooperative/solidarity vendor preferred per CCIN Principle 6.'}"
        ),
        ethical_impact=impact,
        payload={"vendor": selected.get("name"), "tier": selected.get("tier")},
    )

    return {
        **state,
        "selected_vendor": selected,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: Prepare Valueflows/REA order ──────────────────────────────────────


def prepare_order(state: ProcurementState) -> dict[str, Any]:
    """Format the procurement order as a Valueflows REA EconomicEvent."""
    req = state.get("purchase_request", {}) or {}
    vendor = state.get("selected_vendor", {}) or {}
    domain = settings.activitypub_domain

    is_conventional = vendor.get("tier", TIER_CONVENTIONAL) == TIER_CONVENTIONAL

    rea_event = {
        "@context": "https://w3id.org/valueflows",
        "type": "vf:EconomicEvent",
        "id": f"urn:iskander:procurement:{uuid4()}",
        "action": "vf:transfer",
        "provider": {
            "name": vendor.get("name", "unknown"),
            "did": vendor.get("did"),
            "tier": vendor.get("tier"),
        },
        "receiver": {
            "name": f"Cooperative @ {domain}",
            "did": f"did:iskander:node:{domain}",
        },
        "resourceQuantity": {
            "hasUnit": req.get("unit", "unit"),
            "hasNumericalValue": req.get("quantity", 1),
        },
        "resourceConformsTo": {
            "name": req.get("item", "unspecified"),
        },
        "note": req.get("notes", "Procurement order drafted by procurement-agent-v1."),
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Prepare Valueflows/REA procurement order",
        rationale=(
            "Procurement formatted per REA economic vocabulary for "
            "interoperability with federated cooperative networks."
        ),
        ethical_impact=(
            EthicalImpactLevel.HIGH if is_conventional else EthicalImpactLevel.MEDIUM
        ),
        payload={"rea_event_id": rea_event["id"]},
    )

    return {
        **state,
        "rea_order": rea_event,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_procurement_graph():
    """Compile the Procurement Agent LangGraph."""
    g = StateGraph(ProcurementState)
    g.add_node("parse_purchase_request", parse_purchase_request)
    g.add_node("search_cooperative_vendors", search_cooperative_vendors)
    g.add_node("rank_and_select_vendor", rank_and_select_vendor)
    g.add_node("prepare_order", prepare_order)
    g.set_entry_point("parse_purchase_request")
    g.add_edge("parse_purchase_request", "search_cooperative_vendors")
    g.add_edge("search_cooperative_vendors", "rank_and_select_vendor")
    g.add_edge("rank_and_select_vendor", "prepare_order")
    g.add_edge("prepare_order", END)
    return g.compile()


procurement_graph = build_procurement_graph()


# ── Helpers ───────────────────────────────────────────────────────────────────


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
