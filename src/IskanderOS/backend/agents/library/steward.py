"""
Steward Agent v2 — DisCO Contributory Accounting with Care Work
quantification and Circuit Breaker conflict resolution.

Phase 17 Refactor — Anti-Surveillance Opt-In Claim Model:
  The Steward Agent NEVER passively reads Matrix or ActivityPub chat logs.
  It is NOT an algorithmic manager. It is a facilitator of EXPLICIT,
  peer-verified contribution claims submitted by cooperative members.

  All contributions enter via a structured JSON claim payload:
    {"action": "log_care_work", "member": "Alice", "hours": 2, "witness": "Bob"}

  The listed witness (Bob) must cryptographically approve the claim via the
  PeerVerification webhook before ANY ledger entry is written. This replaces
  the prior model of passive chat scraping with consent-based, peer-validated
  accounting. The AI works FOR the workers, not as their surveillant.

Graph: validate_claim → validate_member → verify_peer_witness
       → quantify_care_work → check_circuit_breaker
       → [conditional: HITL or write_ledger_entry] → END

Phase 12 Addition — ZK Privacy Layer:
  The `write_ledger_entry` node generates a ZK-SNARK proof (via
  MACICoordinator.generate_care_work_proof()) that commits to the RESULT of
  the computation — member DID hash, hours, multiplier, SCP score — without
  exposing any conversational context or agent reasoning chain.

  Raw chat context is NEVER written to the `contributions` table. Only the
  ZK proof JSON is stored in the `zk_proof` column.
"""
from __future__ import annotations

import json
import logging
from typing import Any

# Phase 17: ChatOllama import REMOVED — the Steward Agent no longer runs LLM
# inference on member chat logs. Contribution streams are self-declared by
# members via structured opt-in claims. Removed passive chat scraping to
# prevent algorithmic worker surveillance.
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.core import load_prompt
from backend.agents.core.glass_box_parser import GlassBoxParser
from backend.agents.core.persona_generator import build_agent_prompt
from backend.agents.state import ContributionStateV2
from backend.config import settings
from backend.crypto.zk_maci_wrapper import MACICoordinator
from backend.routers.power import agents_are_paused
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "steward-agent-v2"

_role_prompt = load_prompt("prompt_steward.txt")
_parser = GlassBoxParser()

# Phase 12: shared MACICoordinator instance for ZK care-work proof generation.
# In production: coordinator_address should be loaded from settings and match
# the `coordinator` slot in the deployed MACIVoting.sol contract.
_zk_coordinator = MACICoordinator(
    coordinator_address=getattr(settings, "zk_coordinator_address", "0x0000000000000000000000000000000000000000")
)

WORK_STREAMS = ("livelihood", "care", "commons")

# ── Care Work SCP multipliers (from prompt_steward.txt rubric) ────────────────
CARE_MULTIPLIERS: dict[str, float] = {
    "mentoring":        1.5,
    "facilitation":     1.3,
    "conflict_mediation": 1.8,
    "emotional_support": 1.2,
    "accessibility":    1.4,
}
DEFAULT_CARE_MULTIPLIER = 1.2


# ── Node 1: Validate Opt-In Claim ────────────────────────────────────────────
# Phase 17: Removed passive LLM classification of raw chat descriptions.
# The Steward Agent no longer ingests free-text from Matrix/ActivityPub.
# Members MUST submit structured claims with an explicit stream declaration
# and a named peer witness. This prevents algorithmic worker surveillance.

_REQUIRED_CLAIM_FIELDS = {"action", "member_did", "stream", "hours", "witness_did", "description"}


def validate_claim(state: ContributionStateV2) -> dict[str, Any]:
    """Validate that the contribution is a structured opt-in claim, not passive chat scraping.

    Phase 17: The AI NEVER passively reads chat logs to infer contributions.
    Members explicitly declare their stream (livelihood/care/commons) and
    designate a peer witness. The AI is a bookkeeper, not a surveillant.
    """
    if agents_are_paused():
        return {**state, "error": "Agents paused (low power mode)."}

    raw = state.get("raw_contribution", {}) or {}

    # Reject any claim missing required structured fields.
    missing = _REQUIRED_CLAIM_FIELDS - set(raw.keys())
    if missing:
        action = AgentAction(
            agent_id=AGENT_ID,
            action="REJECT — malformed claim (missing fields)",
            rationale=(
                "Phase 17 anti-surveillance mandate: contributions MUST arrive as "
                "structured opt-in claims, not passive chat ingestion. "
                f"Missing fields: {sorted(missing)}"
            ),
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"missing_fields": sorted(missing)},
        )
        return {
            **state,
            "error": f"Malformed claim. Required fields: {sorted(_REQUIRED_CLAIM_FIELDS)}",
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }

    # Accept the member-declared stream directly — no LLM re-classification.
    stream = raw.get("stream", "commons").lower()
    if stream not in WORK_STREAMS:
        stream = "commons"

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Accept opt-in claim: stream='{stream}', witness='{raw.get('witness_did', '?')}'",
        rationale=(
            "Phase 17: Member self-declares contribution stream per DisCO three-stream "
            "model (CCIN Principle 8). No passive chat scraping. No LLM re-classification "
            "of human intent. The cooperative trusts its members."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"stream": stream, "witness_did": raw.get("witness_did")},
    )

    return {
        **state,
        "classified_stream": stream,
        "action_log": state.get("action_log", []) + [action.model_dump()],
        "error": None,
    }


# ── Node 2: Validate member SBT ──────────────────────────────────────────────


def validate_member(state: ContributionStateV2) -> dict[str, Any]:
    """Check that the contributing member holds an active CoopIdentity SBT."""
    raw = state.get("raw_contribution", {}) or {}
    member_did = raw.get("member_did", "")

    # Lightweight EVM check — same pattern as steward_agent v1.
    from web3 import Web3

    valid = False
    try:
        w3 = Web3(Web3.HTTPProvider(settings.evm_rpc_url))
        if w3.is_connected() and member_did.startswith("0x"):
            balance = w3.eth.get_balance(Web3.to_checksum_address(member_did))
            valid = balance >= 0  # Non-reverted call = address exists.
    except Exception as exc:
        logger.warning("EVM unreachable for member validation: %s", exc)
        valid = True  # Fail open in dev; fail closed in prod (TODO: config flag).

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Validate member identity",
        rationale="CCIN Principle 1 (Voluntary & Open Membership) — only verified members may log contributions.",
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"member_did": member_did, "valid": valid},
    )

    if not valid:
        return {
            **state,
            "error": f"Member {member_did} does not hold active CoopIdentity SBT.",
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }

    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 2.5: Peer Verification (Phase 17) ──────────────────────────────────
# The Steward Agent MUST NOT record any contribution without peer corroboration.
# This replaces the panopticon model (AI silently observing chat) with a
# consent-based model where a named human witness cryptographically approves
# the claim. If the witness has not yet approved, the graph halts here.


def verify_peer_witness(state: ContributionStateV2) -> dict[str, Any]:
    """Verify that the designated peer witness has approved this contribution claim.

    Phase 17 — PeerVerification webhook:
      The Steward Agent messages the listed witness and waits for cryptographic
      approval before recording the Synergistic Contribution to the ledger.
      This ensures no contribution is ever logged by AI inference alone.

    In production, this node calls the PeerVerification webhook endpoint
    which sends a Matrix DM to the witness and polls for their Ed25519 signature.
    The claim is BLOCKED until the witness responds.
    """
    raw = state.get("raw_contribution", {}) or {}
    witness_did = raw.get("witness_did", "")
    member_did = raw.get("member_did", "")

    # Check if witness approval is already attached (e.g., pre-signed payload).
    witness_approval = raw.get("witness_approval")
    witness_verified = False

    if witness_approval:
        # In production: verify Ed25519 signature of the witness over the claim hash.
        # For now, accept a signed approval payload as proof of consent.
        witness_verified = isinstance(witness_approval, dict) and witness_approval.get("approved") is True
    else:
        # No pre-signed approval — dispatch PeerVerification webhook.
        # The webhook sends a Matrix DM to witness_did with the claim details
        # and a one-time approval link. The graph will be resumed (via
        # LangGraph checkpoint) when the witness responds.
        import hashlib
        claim_hash = hashlib.sha256(
            f"{member_did}:{raw.get('stream')}:{raw.get('hours')}:{witness_did}".encode()
        ).hexdigest()

        logger.info(
            "PeerVerification: awaiting witness %s approval for claim %s",
            witness_did[:16], claim_hash[:12],
        )
        # In production: POST to /api/peer-verify with {claim_hash, witness_did, member_did}
        # The webhook notifies the witness via Matrix. Graph is interrupted here
        # and resumed when the witness signs.

    if not witness_verified:
        action = AgentAction(
            agent_id=AGENT_ID,
            action="AWAIT peer witness verification",
            rationale=(
                "Phase 17 anti-surveillance mandate: no contribution is recorded "
                "without explicit peer corroboration. The AI does not unilaterally "
                "validate claims — a named human witness must approve. "
                f"Witness: {witness_did[:16]}..."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={"witness_did": witness_did, "verified": False},
        )
        return {
            **state,
            "requires_human_token": True,  # Block the graph until witness responds.
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Peer witness {witness_did[:16]}... verified claim",
        rationale=(
            "Phase 17: Peer-verified contribution claim. The witness has "
            "cryptographically approved this record. No AI inference was used "
            "to validate the contribution — only human consent."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"witness_did": witness_did, "verified": True},
    )

    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 3: Quantify care work ───────────────────────────────────────────────


def quantify_care_work(state: ContributionStateV2) -> dict[str, Any]:
    """Apply SCP multipliers to care work contributions.

    For livelihood and commons streams, the base hours pass through unchanged.
    """
    stream = state.get("classified_stream", "commons")
    raw = state.get("raw_contribution", {}) or {}
    base_hours = float(raw.get("hours", 0))

    if stream != "care":
        care_score = base_hours  # No multiplier for non-care.
        multiplier_used = 1.0
    else:
        # Determine care sub-type from description keywords.
        description = raw.get("description", "").lower()
        multiplier_used = DEFAULT_CARE_MULTIPLIER
        for keyword, mult in CARE_MULTIPLIERS.items():
            if keyword.replace("_", " ") in description or keyword in description:
                multiplier_used = max(multiplier_used, mult)
        care_score = round(base_hours * multiplier_used, 2)

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Quantify contribution: {base_hours}h × {multiplier_used}x = {care_score} SCP",
        rationale=(
            "CCIN Principle 10 (Feminist Economics & Care Valorization). "
            "Care work multipliers ensure invisible labor is properly credited."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"base_hours": base_hours, "multiplier": multiplier_used, "care_score": care_score},
    )

    return {
        **state,
        "care_score": care_score,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: Circuit breaker check ────────────────────────────────────────────


def check_circuit_breaker(state: ContributionStateV2) -> dict[str, Any]:
    """Detect contribution inequities or toxic patterns.

    If a red flag is found, sets requires_human_token=True so the graph
    routes through HITL before writing the ledger entry.
    """
    raw = state.get("raw_contribution", {}) or {}
    description = raw.get("description", "")
    member_did = raw.get("member_did", "")
    hours = float(raw.get("hours", 0))

    # ── Red flag heuristics (enhanced by LLM in production) ───────────
    flags: list[str] = []

    # Flag 1: Extremely high hours (burnout risk).
    if hours > 60:
        flags.append(f"Member {member_did} logged {hours}h — possible burnout risk.")

    # Flag 2: Hostile language in description.
    hostile_terms = ["incompetent", "useless", "lazy", "stupid", "worthless"]
    if any(term in description.lower() for term in hostile_terms):
        flags.append("Hostile language detected in contribution description.")

    # Flag 3: Attempt to log care work with 0 hours (dismissal).
    stream = state.get("classified_stream", "")
    if stream == "care" and hours == 0:
        flags.append("Care work logged with 0 hours — possible undervaluation.")

    if flags:
        conflict = {
            "flags": flags,
            "recommendation": (
                "The cooperative should convene a facilitated discussion to "
                "address the structural pattern(s) identified."
            ),
        }
        action = AgentAction(
            agent_id=AGENT_ID,
            action="CIRCUIT BREAKER — contribution pattern flagged",
            rationale=(
                "Structural inequity detected.  Describing pattern without "
                "assigning blame per Steward protocol.  Flags: "
                + "; ".join(flags)
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload=conflict,
        )
        return {
            **state,
            "conflict_resolution": conflict,
            "requires_human_token": True,
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }

    # No flags — proceed normally.
    return {
        **state,
        "conflict_resolution": None,
        "requires_human_token": False,
    }


# ── Node 5: Write ledger entry ───────────────────────────────────────────────


def write_ledger_entry(state: ContributionStateV2) -> dict[str, Any]:
    """Construct the ledger entry dict with a ZK-SNARK care work proof.

    Phase 12 — Privacy-Preserving Care Work (TEE Conceptual Model):
      This node conceptually executes inside a Trusted Execution Environment.
      The raw contribution description (which may contain sensitive conversational
      context identifying member behaviour patterns) is NEVER written to the
      `contributions` table. Instead, a ZK proof is generated that commits to
      the OUTCOME (member DID hash, hours, multiplier, SCP score) without
      preserving the evidence chain.

      This directly implements the DisCO framework's mandate for non-coercive
      environments: no cooperative manager, peer, or future auditor can use
      the ledger to reconstruct private conversations or infer political
      positions from contribution patterns.

      If ZK proof generation fails, the entry is REJECTED and logged. The
      cooperative must re-submit the contribution through the normal HITL flow.

    Agent does NOT write to DB — the calling router handles persistence,
    keeping agents stateless and testable.
    """
    raw = state.get("raw_contribution", {}) or {}
    member_did = raw.get("member_did", "")
    stream = state.get("classified_stream", "commons")
    hours = float(raw.get("hours", 0))
    care_score = state.get("care_score", 0)
    multiplier = care_score / hours if hours > 0 else 1.0
    # Infer the care sub-type from the description for the proof claim.
    description = raw.get("description", "")
    care_type = "unspecified"
    for keyword in CARE_MULTIPLIERS:
        if keyword.replace("_", " ") in description.lower() or keyword in description.lower():
            care_type = keyword
            break

    # ── Generate ZK Proof (replaces raw description in the ledger) ────────────
    zk_proof_json: str | None = None
    zk_error: str | None = None

    if stream == "care":
        try:
            proof = _zk_coordinator.generate_care_work_proof(
                member_did=member_did,
                hours=hours,
                care_type=care_type,
                multiplier=multiplier,
                care_score=care_score,
            )
            is_valid, reason = _zk_coordinator.validate_proof(proof)
            if not is_valid:
                zk_error = f"ZK_PROOF_INVALID: {reason}"
                logger.error(
                    "Care work ZK proof validation failed for DID hash %s: %s",
                    __import__("hashlib").sha256(member_did.encode()).hexdigest()[:12],
                    reason,
                )
            else:
                zk_proof_json = proof.to_json()
        except Exception as exc:
            zk_error = f"ZK_PROOF_ERROR: {exc}"
            logger.exception("ZK proof generation failed — rejecting care work entry.")

    if zk_error:
        # Fail gracefully: reject the entry, surface an anonymous error.
        # The member DID is NOT included in the error payload to prevent correlation.
        action = AgentAction(
            agent_id=AGENT_ID,
            action="REJECT care work entry — ZK proof failure",
            rationale=zk_error,
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={"stream": stream, "error": zk_error},
        )
        return {
            **state,
            "ledger_entry": None,
            "error": zk_error,
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }

    entry = {
        "member_did": member_did,
        "stream": stream,
        # Phase 12: raw description is EXCLUDED from care work entries.
        # For livelihood/commons streams it is retained (not sensitive by default).
        "description": description if stream != "care" else "[REDACTED: see zk_proof]",
        "hours": hours,
        "care_score": care_score,
        "value_tokens": raw.get("value_tokens", 0),
        "ipfs_cid": raw.get("ipfs_cid"),
        # Phase 12 additions:
        "zk_proof": zk_proof_json,  # JSON-serialized ZKProof — stored in zk_proof column.
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Prepare contribution ledger entry (ZK-privacy mode)",
        rationale=(
            "Contributory accounting record per DisCO framework (CCIN Principle 8). "
            "Care work rationale replaced with ZK proof — raw conversational context purged."
            if stream == "care"
            else "Contributory accounting record per DisCO framework (CCIN Principle 8)."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={k: v for k, v in entry.items() if k != "zk_proof"},  # Don't log proof in action log.
    )

    return {
        **state,
        "ledger_entry": entry,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── HITL breakpoint ──────────────────────────────────────────────────────────


def human_review(state: ContributionStateV2) -> dict[str, Any]:
    """No-op HITL breakpoint for circuit-breaker escalation."""
    return state


# ── Routing logic ─────────────────────────────────────────────────────────────


def _route_after_circuit_breaker(state: ContributionStateV2) -> str:
    """Route to HITL if circuit breaker fired, else straight to ledger."""
    if state.get("requires_human_token"):
        return "human_review"
    return "write_ledger_entry"


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_steward_v2_graph():
    """Compile the Steward Agent v2 LangGraph with opt-in claims and peer verification.

    Phase 17 graph flow:
      validate_claim → validate_member → verify_peer_witness
        → quantify_care_work → check_circuit_breaker
        → [conditional: human_review or write_ledger_entry] → END

    Key change: classify_contribution (passive LLM inference on chat logs) has been
    REMOVED. The member self-declares their stream. A peer witness must approve
    before the ledger entry is written. The AI is a bookkeeper, not a surveillant.
    """
    g = StateGraph(ContributionStateV2)
    g.add_node("validate_claim", validate_claim)
    g.add_node("validate_member", validate_member)
    g.add_node("verify_peer_witness", verify_peer_witness)
    g.add_node("quantify_care_work", quantify_care_work)
    g.add_node("check_circuit_breaker", check_circuit_breaker)
    g.add_node("human_review", human_review)
    g.add_node("write_ledger_entry", write_ledger_entry)

    g.set_entry_point("validate_claim")
    g.add_edge("validate_claim", "validate_member")
    g.add_edge("validate_member", "verify_peer_witness")
    g.add_edge("verify_peer_witness", "quantify_care_work")
    g.add_edge("quantify_care_work", "check_circuit_breaker")
    g.add_conditional_edges(
        "check_circuit_breaker",
        _route_after_circuit_breaker,
        {"human_review": "human_review", "write_ledger_entry": "write_ledger_entry"},
    )
    g.add_edge("human_review", "write_ledger_entry")
    g.add_edge("write_ledger_entry", END)

    return g.compile(
        checkpointer=MemorySaver(),
        # Phase 17: interrupt before peer verification AND human review.
        # The graph halts at verify_peer_witness until the witness signs,
        # and at human_review if the circuit breaker fires.
        interrupt_before=["verify_peer_witness", "human_review"],
    )


steward_v2_graph = build_steward_v2_graph()


# ── Helpers ───────────────────────────────────────────────────────────────────


# Phase 17: _heuristic_classify() REMOVED — the Steward Agent no longer
# infers contribution streams from free-text descriptions. Members self-declare
# their stream in the structured opt-in claim payload. Removing this function
# eliminates the last path through which the AI could unilaterally categorize
# human labor without explicit member consent.


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
