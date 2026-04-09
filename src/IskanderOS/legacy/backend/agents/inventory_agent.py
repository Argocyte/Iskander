"""
Web3 Inventory Agent — Valueflows / REA Economic Model

Queries on-chain balances and formats them as REA (Resource-Event-Agent)
economic resources per the Valueflows vocabulary standard.

REA model:
  - Resource : something of value (ERC-20 token, ETH, SBT count)
  - Event    : an economic event affecting a resource (transfer, mint, burn)
  - Agent    : the cooperative or member controlling the resource

LangGraph graph:
  fetch_onchain_resources → format_rea_report → [END]

The agent is read-only and cannot submit transactions.
All actions logged via Glass Box Protocol.
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from backend.agents.state import InventoryState
from backend.config import settings
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = structlog.get_logger(__name__)

AGENT_ID = "inventory-agent-v1"

# ── Valueflows resource type constants ────────────────────────────────────────
VF_RESOURCE_TYPES = {
    "native_token":  "vf:EconomicResource",
    "erc20":         "vf:EconomicResource",
    "sbt":           "vf:EconomicResource",
}


# ── Nodes ─────────────────────────────────────────────────────────────────────

def fetch_onchain_resources(state: InventoryState) -> InventoryState:
    """
    Node 1: Fetch on-chain balances via web3.py.

    Reads ETH balance and any registered ERC-20 token balances for the
    cooperative's Safe multi-sig address. EVM calls are read-only (eth_call).
    Respects power-aware degradation: exits early if system is in low-power mode.
    """
    from backend.routers.power import agents_are_paused
    if agents_are_paused():
        logger.warning("inventory_agent_paused_low_power")
        return {
            **state,
            "resources":  [{"vf:name": "Agent paused", "vf:note": "System is in low-power mode."}],
            "rea_report": {"iskander:summary": "_Inventory agent paused: low-power mode active._"},
        }

    from web3 import Web3

    rpc = Web3(Web3.HTTPProvider(settings.evm_rpc_url))
    safe_address = settings.safe_address

    resources: list[dict[str, Any]] = []

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Fetch on-chain resources for Safe {safe_address}",
        rationale="Inventory agent performing scheduled read of cooperative treasury assets.",
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"safe_address": safe_address, "rpc_url": settings.evm_rpc_url},
    )

    try:
        if not rpc.is_connected():
            raise ConnectionError(f"Cannot connect to EVM node at {settings.evm_rpc_url}")

        eth_balance_wei = rpc.eth.get_balance(
            Web3.to_checksum_address(safe_address)
        )
        resources.append({
            "@type":         VF_RESOURCE_TYPES["native_token"],
            "vf:name":       "Native Token (ETH/xDAI)",
            "vf:quantity": {
                "om2:hasNumericalValue": str(Web3.from_wei(eth_balance_wei, "ether")),
                "om2:hasUnit":           "ETH",
            },
            "vf:accountingQuantity": eth_balance_wei,
            "iskander:safeAddress":  safe_address,
            "iskander:chainId":      settings.evm_chain_id,
        })

        logger.info("inventory_fetch_success", address=safe_address, eth=str(Web3.from_wei(eth_balance_wei, "ether")))

    except Exception as exc:
        logger.warning("inventory_fetch_error", error=str(exc))
        # Return empty resources; agent gracefully degrades
        resources.append({
            "@type":    "vf:EconomicResource",
            "vf:name":  "EVM node unavailable",
            "vf:note":  str(exc),
        })

    return {
        **state,
        "resources":   resources,
        "action_log":  state.get("action_log", []) + [action.model_dump(mode="json")],
    }


def format_rea_report(state: InventoryState) -> InventoryState:
    """
    Node 2: Use Llama 3 via Ollama to generate a human-readable
    Valueflows REA summary from the raw on-chain resource data.

    Falls back to a structured dict if Ollama is unavailable.
    """
    resources = state.get("resources", [])

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Format REA inventory report via local LLM",
        rationale="Translating raw EVM data into a Valueflows-compliant REA report for member transparency.",
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"resource_count": len(resources)},
    )

    prompt = (
        "You are a cooperative accountant. Format the following on-chain economic resources "
        "as a concise Valueflows REA inventory report in Markdown. "
        "Include: resource name, quantity, unit, and a one-sentence economic interpretation.\n\n"
        f"Resources:\n{resources}"
    )

    report_text: str
    try:
        llm = ChatOllama(base_url=settings.ollama_base_url, model=settings.ollama_model)
        response = llm.invoke([
            SystemMessage(content="You are a cooperative accountant following the Valueflows REA standard."),
            HumanMessage(content=prompt),
        ])
        report_text = response.content
    except Exception as exc:
        logger.warning("llm_unavailable_fallback", error=str(exc))
        report_text = "\n".join(
            f"- **{r.get('vf:name', 'Unknown')}**: {r.get('vf:quantity', r.get('vf:note', 'N/A'))}"
            for r in resources
        )

    rea_report = {
        "@context": {
            "vf":      "https://w3id.org/valueflows#",
            "om2":     "http://www.ontology-of-units-of-measure.org/resource/om-2/",
            "iskander": "https://iskander.local/vocab#",
        },
        "vf:inventoryReport": resources,
        "iskander:summary":   report_text,
        "iskander:agentId":   AGENT_ID,
    }

    return {
        **state,
        "rea_report": rea_report,
        "action_log": state.get("action_log", []) + [action.model_dump(mode="json")],
    }


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_inventory_graph() -> Any:
    g = StateGraph(InventoryState)
    g.add_node("fetch_onchain_resources", fetch_onchain_resources)
    g.add_node("format_rea_report",       format_rea_report)
    g.set_entry_point("fetch_onchain_resources")
    g.add_edge("fetch_onchain_resources", "format_rea_report")
    g.add_edge("format_rea_report",       END)
    return g.compile()


inventory_graph = build_inventory_graph()
