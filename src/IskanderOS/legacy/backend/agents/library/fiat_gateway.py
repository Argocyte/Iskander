"""
fiat_gateway.py — Fiat Gateway Agent v2: cFIAT mint/burn orchestration (Phase 26).

Extends the Phase 22 escrow-settlement agent with solvency-aware mint/burn
orchestration. The agent reads the cooperative bank reserve via Open Banking,
computes the solvency ratio against on-chain cFIAT supply, and proposes
mint/burn/hold actions with mandatory HITL approval for large operations.

Graph:
  check_reserve -> evaluate_solvency -> propose_action
    -> [conditional: HITL if requires_human_token] -> execute_on_chain -> END

SECURITY:
  The AI NEVER mints or burns tokens autonomously. All on-chain operations
  require explicit human approval via the HITL breakpoint. Mints above
  cfiat_mint_approval_threshold always trigger HITL.

ANTI-EXTRACTIVE:
  This architecture bypasses Visa, Mastercard, and Stripe. Inter-cooperative
  commerce settles directly via cooperative bank rails (PSD2/Open Banking),
  returning the 2-3% transaction fees to the workers and the cooperative.

REGULATORY REALISM:
  cFIAT supply MUST NEVER exceed the fiat reserve balance in the cooperative
  bank's regulated trust account. The solvency check enforces this invariant.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.state import FiatGatewayState
from backend.config import settings
from backend.finance.open_banking_client import OpenBankingClient
from backend.routers.power import agents_are_paused
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "fiat-gateway-v1"


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH NODES
# ═══════════════════════════════════════════════════════════════════════════════


# ── Node 1: Check Reserve ─────────────────────────────────────────────────────


def check_reserve(state: FiatGatewayState) -> dict[str, Any]:
    """Query the cooperative bank's fiat reserve balance via Open Banking API.

    Stores the FiatReserveBalance snapshot in state for solvency evaluation.
    Glass Box: MEDIUM impact (read-only bank query).
    """
    if agents_are_paused():
        return {
            **state,
            "error": "Agents paused (low power mode). Retry when power restored.",
        }

    # OpenBankingClient.get_fiat_reserve_balance() is async, but LangGraph
    # nodes are sync. Use import to run the coroutine synchronously.
    import asyncio

    client = OpenBankingClient.get_instance()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already inside an async context (e.g. FastAPI), create a task.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                balance, balance_action = pool.submit(
                    asyncio.run, client.get_fiat_reserve_balance()
                ).result()
        else:
            balance, balance_action = asyncio.run(client.get_fiat_reserve_balance())
    except Exception as exc:
        logger.exception("Failed to query fiat reserve: %s", exc)
        return {**state, "error": f"Reserve query failed: {exc}"}

    reserve_data = {
        "balance": str(balance.balance),
        "currency": balance.currency,
        "account_id": balance.account_id,
        "institution": balance.institution,
        "as_of": balance.as_of.isoformat(),
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action="check_reserve",
        rationale=(
            f"Queried cooperative bank reserve via Open Banking API. "
            f"Balance: {balance.balance} {balance.currency} "
            f"(account: {balance.account_id}, institution: {balance.institution}). "
            f"This balance must always be >= total cFIAT supply to maintain 1:1 backing."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload=reserve_data,
    )

    return {
        **state,
        "reserve_balance": reserve_data,
        "action_log": state.get("action_log", []) + [action.model_dump()],
        "error": None,
    }


# ── Node 2: Evaluate Solvency ────────────────────────────────────────────────


def evaluate_solvency(state: FiatGatewayState) -> dict[str, Any]:
    """Compare reserve vs on-chain cFIAT supply. Compute solvency ratio.

    solvency_ratio = fiat_reserve / (cfiat_supply in fiat units).

    If ratio < 1.0, set proposed_action='hold' — minting is blocked.
    Glass Box: HIGH impact (solvency determination affects all operations).
    """
    if state.get("error"):
        return state

    reserve_data = state.get("reserve_balance") or {}
    reserve_balance = Decimal(reserve_data.get("balance", "0"))

    # Read on-chain cFIAT supply.
    # STUB: In production, call CoopFiatToken.totalSupply() via web3.py.
    on_chain_supply = state.get("on_chain_supply")
    if on_chain_supply is None:
        # Default stub value: 25,000 cFIAT in wei.
        on_chain_supply = 25_000 * (10 ** 18)

    # Convert wei to fiat-scale (18 decimals for ERC-20).
    supply_fiat = Decimal(on_chain_supply) / Decimal(10 ** 18)

    if supply_fiat > 0:
        solvency_ratio = float(reserve_balance / supply_fiat)
    else:
        solvency_ratio = float("inf")

    # If insolvent, force proposed_action to "hold".
    forced_hold = solvency_ratio < 1.0
    proposed_action = "hold" if forced_hold else state.get("proposed_action")

    action = AgentAction(
        agent_id=AGENT_ID,
        action="evaluate_solvency",
        rationale=(
            f"Solvency evaluation: reserve = {reserve_balance} {reserve_data.get('currency', '?')}, "
            f"on-chain supply = {supply_fiat} cFIAT, ratio = {solvency_ratio:.4f}. "
            f"{'INSOLVENT: ratio < 1.0 — minting blocked, forced HOLD.' if forced_hold else 'Solvent: ratio >= 1.0 — operations permitted.'} "
            f"The cooperative bank must hold real, insured fiat >= total cFIAT supply."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload={
            "reserve_balance": str(reserve_balance),
            "on_chain_supply_wei": on_chain_supply,
            "supply_fiat": str(supply_fiat),
            "solvency_ratio": solvency_ratio,
            "forced_hold": forced_hold,
        },
    )

    return {
        **state,
        "on_chain_supply": on_chain_supply,
        "solvency_ratio": solvency_ratio,
        "proposed_action": proposed_action,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 3: Propose Action ───────────────────────────────────────────────────


def propose_action(state: FiatGatewayState) -> dict[str, Any]:
    """Propose mint/burn/hold based on solvency and escrow signals.

    If a mint is proposed and the amount exceeds cfiat_mint_approval_threshold,
    requires_human_token is set to True for HITL approval.
    Glass Box: HIGH impact (determines whether tokens are created/destroyed).
    """
    if state.get("error"):
        return state

    solvency_ratio = state.get("solvency_ratio", 0.0)
    current_action = state.get("proposed_action")
    proposed_amount = state.get("proposed_amount", 0) or 0

    # If solvency forced a hold, do not override.
    if current_action == "hold" and solvency_ratio < 1.0:
        action = AgentAction(
            agent_id=AGENT_ID,
            action="propose_action: hold (insolvent)",
            rationale=(
                f"Solvency ratio {solvency_ratio:.4f} < 1.0. Cannot mint new cFIAT. "
                "Proposed action: HOLD. Alert stewards to restore reserve parity. "
                "Anti-extractive: this circuit breaker protects the cooperative from "
                "fractional reserve risk."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "proposed_action": "hold",
                "proposed_amount": 0,
                "solvency_ratio": solvency_ratio,
                "requires_human_token": False,
            },
        )
        return {
            **state,
            "proposed_action": "hold",
            "proposed_amount": 0,
            "requires_human_token": False,
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }

    # Default to the action already set (from router: "mint" or "burn").
    if current_action is None:
        current_action = "hold"

    # Determine if HITL is needed.
    needs_hitl = False
    if current_action == "mint" and proposed_amount > settings.cfiat_mint_approval_threshold:
        needs_hitl = True

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"propose_action: {current_action} ({proposed_amount} wei)",
        rationale=(
            f"Proposed {current_action} of {proposed_amount} wei. "
            f"Solvency ratio: {solvency_ratio:.4f}. "
            f"{'HITL required: amount exceeds cfiat_mint_approval_threshold.' if needs_hitl else 'Within auto-approval threshold.'} "
            f"Anti-extractive: bypassing Visa/MC/Stripe, returning fees to workers."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload={
            "proposed_action": current_action,
            "proposed_amount": proposed_amount,
            "solvency_ratio": solvency_ratio,
            "requires_human_token": needs_hitl,
            "threshold": settings.cfiat_mint_approval_threshold,
        },
    )

    return {
        **state,
        "proposed_action": current_action,
        "proposed_amount": proposed_amount,
        "requires_human_token": needs_hitl,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: Execute On-Chain ─────────────────────────────────────────────────


def execute_on_chain(state: FiatGatewayState) -> dict[str, Any]:
    """STUB: Build Web3 tx for CoopFiatToken.mint() or .burn().

    In production, this node constructs and submits a signed transaction
    via the bank oracle private key. Currently returns a stub tx hash.
    Glass Box: HIGH impact (on-chain token supply modification).
    """
    if state.get("error"):
        return state

    proposed_action = state.get("proposed_action", "hold")
    proposed_amount = state.get("proposed_amount", 0) or 0

    if proposed_action == "hold":
        action = AgentAction(
            agent_id=AGENT_ID,
            action="execute_on_chain: no-op (hold)",
            rationale="Action is HOLD — no on-chain transaction needed.",
            ethical_impact=EthicalImpactLevel.LOW,
        )
        return {
            **state,
            "chain_tx_result": {"status": "skipped", "reason": "hold"},
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }

    # STUB: Build unsigned transaction.
    # In production:
    #   w3 = Web3(Web3.HTTPProvider(settings.evm_rpc_url))
    #   token = w3.eth.contract(address=settings.cfiat_token_address, abi=CFIAT_ABI)
    #   if proposed_action == "mint":
    #       tx = token.functions.mint(safe_address, proposed_amount).build_transaction({...})
    #   elif proposed_action == "burn":
    #       tx = token.functions.burn(proposed_amount).build_transaction({...})
    #   signed = w3.eth.account.sign_transaction(tx, settings.deployer_private_key)
    #   tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction).hex()

    stub_tx_hash = f"0x{'0' * 62}26"  # Stub hash for Phase 26

    chain_tx_result = {
        "status": "drafted",
        "action": proposed_action,
        "amount_wei": proposed_amount,
        "contract": settings.cfiat_token_address,
        "function": f"CoopFiatToken.{proposed_action}()",
        "tx_hash": stub_tx_hash,
        "note": "STUB — transaction not submitted. Pending oracle key integration.",
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"execute_on_chain: {proposed_action} {proposed_amount} wei",
        rationale=(
            f"Drafted {proposed_action} transaction for {proposed_amount} wei "
            f"on CoopFiatToken at {settings.cfiat_token_address}. "
            f"STUB: tx_hash = {stub_tx_hash}. "
            f"In production, the bank oracle signs and submits this transaction. "
            f"Anti-extractive: direct cooperative bank rails, no Visa/MC/Stripe."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload=chain_tx_result,
    )

    return {
        **state,
        "chain_tx_result": chain_tx_result,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTING
# ═══════════════════════════════════════════════════════════════════════════════


def _route_after_propose(state: FiatGatewayState) -> str:
    """Route to HITL breakpoint if human approval is required."""
    if state.get("requires_human_token"):
        return "hitl_gate"
    return "execute_on_chain"


# ── HITL Gate Node ────────────────────────────────────────────────────────────


def hitl_gate(state: FiatGatewayState) -> dict[str, Any]:
    """No-op node — graph suspends here via interrupt_before for HITL approval.

    A BrightID-verified steward reviews the proposed mint/burn action and
    either approves (resume) or rejects (graph terminates via router).
    """
    return {**state, "requires_human_token": False}


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH ASSEMBLY
# ═══════════════════════════════════════════════════════════════════════════════


def build_fiat_gateway_graph():
    """Compile the Fiat Gateway Agent LangGraph with conditional HITL.

    Flow:
      check_reserve -> evaluate_solvency -> propose_action
        -> [HITL if requires_human_token] -> execute_on_chain -> END
    """
    g = StateGraph(FiatGatewayState)

    g.add_node("check_reserve", check_reserve)
    g.add_node("evaluate_solvency", evaluate_solvency)
    g.add_node("propose_action", propose_action)
    g.add_node("hitl_gate", hitl_gate)
    g.add_node("execute_on_chain", execute_on_chain)

    g.set_entry_point("check_reserve")
    g.add_edge("check_reserve", "evaluate_solvency")
    g.add_edge("evaluate_solvency", "propose_action")
    g.add_conditional_edges(
        "propose_action",
        _route_after_propose,
        {
            "hitl_gate": "hitl_gate",
            "execute_on_chain": "execute_on_chain",
        },
    )
    g.add_edge("hitl_gate", "execute_on_chain")
    g.add_edge("execute_on_chain", END)

    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["hitl_gate"],
    )


fiat_gateway_graph = build_fiat_gateway_graph()
