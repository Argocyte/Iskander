"""
solvency_oracle.py — Phase 26: Solvency Oracle for cFIAT 1:1 Reserve Enforcement.

Reads the cooperative bank reserve balance via Open Banking API and compares
it against the on-chain cFIAT supply and escrow totals. If the solvency
ratio drops below 1.0, the circuit breaker activates and blocks new mints.

REGULATORY REALISM:
  Every cFIAT token MUST be backed 1:1 by real fiat in a regulated trust
  account. This oracle enforces that invariant and provides on-chain
  attestation via StewardshipLedger.updateFiatReserve().

ANTI-EXTRACTIVE:
  The oracle exists so the cooperative can self-audit its reserve ratio
  without relying on extractive third-party auditors or opaque stablecoin
  issuers. Full Glass Box transparency on every check.

STUB NOTICE:
  On-chain reads (cFIAT supply, escrow totals) are mocked. In production,
  replace with web3.py calls to CoopFiatToken.totalSupply() and
  IskanderEscrow balance queries.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from backend.config import settings
from backend.finance.open_banking_client import OpenBankingClient
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "solvency-oracle-v1"


@dataclass
class SolvencySnapshot:
    """Point-in-time solvency status of the cFIAT system."""
    fiat_reserve: Decimal
    total_escrow_wei: int
    cfiat_supply_wei: int
    solvency_ratio: float
    circuit_breaker_active: bool


class SolvencyOracle:
    """Reads bank reserve + on-chain state and computes solvency ratio.

    Singleton: obtain via SolvencyOracle.get_instance().

    Two capabilities:
      1. check_solvency() — read-only snapshot of reserve vs supply.
      2. push_to_chain()   — STUB: attest reserve data on-chain.
    """

    _instance: "SolvencyOracle | None" = None

    @classmethod
    def get_instance(cls) -> "SolvencyOracle":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Read: Solvency Check ──────────────────────────────────────────────────

    async def check_solvency(self) -> tuple[SolvencySnapshot, AgentAction]:
        """Compute the current solvency ratio.

        solvency_ratio = fiat_reserve / (cfiat_supply converted to fiat units).

        If ratio < 1.0 the circuit breaker activates: no new mints allowed.

        Returns (SolvencySnapshot, AgentAction) for Glass Box audit.
        """
        # Step 1: Read bank reserve via Open Banking API.
        client = OpenBankingClient.get_instance()
        balance, _balance_action = await client.get_fiat_reserve_balance()
        fiat_reserve = balance.balance

        # Step 2: Read on-chain cFIAT total supply.
        # STUB: In production, call CoopFiatToken.totalSupply() via web3.py.
        # w3 = Web3(Web3.HTTPProvider(settings.evm_rpc_url))
        # token = w3.eth.contract(address=settings.cfiat_token_address, abi=CFIAT_ABI)
        # cfiat_supply_wei = token.functions.totalSupply().call()
        cfiat_supply_wei = 25_000 * (10 ** 18)  # STUB: 25,000 cFIAT

        # Step 3: Read on-chain escrow totals.
        # STUB: In production, sum all active IskanderEscrow cFIAT balances.
        total_escrow_wei = 5_000 * (10 ** 18)  # STUB: 5,000 cFIAT in escrow

        # Step 4: Compute ratio.
        # Convert wei supply to fiat-scale (18 decimals for ERC-20).
        cfiat_supply_fiat = Decimal(cfiat_supply_wei) / Decimal(10 ** 18)

        if cfiat_supply_fiat > 0:
            solvency_ratio = float(fiat_reserve / cfiat_supply_fiat)
        else:
            # No supply minted yet — fully solvent by definition.
            solvency_ratio = float("inf")

        circuit_breaker_active = solvency_ratio < 1.0

        snapshot = SolvencySnapshot(
            fiat_reserve=fiat_reserve,
            total_escrow_wei=total_escrow_wei,
            cfiat_supply_wei=cfiat_supply_wei,
            solvency_ratio=solvency_ratio,
            circuit_breaker_active=circuit_breaker_active,
        )

        action = AgentAction(
            agent_id=AGENT_ID,
            action="check_solvency",
            rationale=(
                f"Solvency check: fiat reserve = {fiat_reserve} {settings.cfiat_currency}, "
                f"cFIAT supply = {cfiat_supply_fiat} (on-chain), "
                f"escrow = {Decimal(total_escrow_wei) / Decimal(10 ** 18)}. "
                f"Ratio = {solvency_ratio:.4f}. "
                f"Circuit breaker {'ACTIVE — minting halted' if circuit_breaker_active else 'inactive — system healthy'}. "
                "Every cFIAT token must be backed 1:1 by real fiat in the cooperative "
                "bank trust account. This is NOT fractional reserve."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "fiat_reserve": str(fiat_reserve),
                "cfiat_supply_wei": cfiat_supply_wei,
                "total_escrow_wei": total_escrow_wei,
                "solvency_ratio": solvency_ratio,
                "circuit_breaker_active": circuit_breaker_active,
            },
        )

        if circuit_breaker_active:
            logger.warning(
                "CIRCUIT BREAKER ACTIVE: solvency ratio %.4f < 1.0. "
                "Reserve: %s, Supply: %s. Minting halted.",
                solvency_ratio, fiat_reserve, cfiat_supply_fiat,
            )
        else:
            logger.info(
                "Solvency OK: ratio %.4f. Reserve: %s, Supply: %s.",
                solvency_ratio, fiat_reserve, cfiat_supply_fiat,
            )

        return snapshot, action

    # ── Write: Push attestation to chain ──────────────────────────────────────

    async def push_to_chain(self) -> dict[str, Any]:
        """STUB: Attest reserve and escrow data on-chain.

        In production, calls:
          StewardshipLedger.updateFiatReserve(reserve_bps)
          StewardshipLedger.updateTotalEscrow(escrow_wei)

        via web3.py with the oracle private key.
        """
        snapshot, _action = await self.check_solvency()

        # STUB: Build unsigned transactions.
        # w3 = Web3(Web3.HTTPProvider(settings.evm_rpc_url))
        # ledger = w3.eth.contract(
        #     address=settings.stewardship_ledger_address,
        #     abi=STEWARDSHIP_LEDGER_ABI,
        # )
        # tx1 = ledger.functions.updateFiatReserve(
        #     int(snapshot.fiat_reserve * 100)  # basis points
        # ).build_transaction({...})
        # tx2 = ledger.functions.updateTotalEscrow(
        #     snapshot.total_escrow_wei
        # ).build_transaction({...})

        result = {
            "status": "drafted",
            "contract": settings.stewardship_ledger_address,
            "functions": ["updateFiatReserve", "updateTotalEscrow"],
            "fiat_reserve": str(snapshot.fiat_reserve),
            "total_escrow_wei": snapshot.total_escrow_wei,
            "solvency_ratio": snapshot.solvency_ratio,
            "note": "STUB — transactions not submitted. Pending oracle key integration.",
        }

        logger.info(
            "Drafted on-chain attestation: reserve=%s, escrow=%d wei",
            snapshot.fiat_reserve, snapshot.total_escrow_wei,
        )

        return result
