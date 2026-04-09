"""
diplomacy.py — Diplomatic Embassy API Router.

Endpoints for the Foreign Reputation System (FRS), Ingestion Embassy
(quarantine sandbox), and Researcher-in-the-Loop (RITL) peer review.

All external knowledge enters through this router. The flow:
  1. Register foreign SDC → establish FRS profile
  2. Record Valueflows transactions → update reputation score
  3. Ingest external asset → quarantine sandbox with collision detection
  4. Submit for peer review → RITL PeerReviewGraph
  5. Admit/reject → promote to KnowledgeAsset or leave in sandbox
"""
from __future__ import annotations

import base64
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from backend.agents.research.ritl_manager import peer_review_graph
from backend.auth.dependencies import AuthenticatedUser, require_role
from backend.diplomacy.identity_attestation_agent import IdentityAttestationAgent
from backend.diplomacy.vc_verifier import TrustRegistryClient, VCVerifier
from backend.finance.frs_client import FRSClient
from backend.mesh.ingestion_embassy import IngestionEmbassy
from backend.schemas.diplomacy import (
    AttestationResponse,
    IngestCredentialRequest,
    IngestCredentialResponse,
    IngestExternalAssetRequest,
    IngestExternalAssetResponse,
    PeerReviewResponse,
    RecordTransactionRequest,
    RegisterSDCRequest,
    RegisterSDCResponse,
    RevokeIssuerRequest,
    RevokeIssuerResponse,
    SubmitForReviewRequest,
    VerifyCredentialRequest,
    VerifyCredentialResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diplomacy", tags=["diplomatic-embassy"])


# ── POST /diplomacy/sdc/register ─────────────────────────────────────────────

@router.post("/sdc/register", response_model=RegisterSDCResponse)
async def register_sdc(
    req: RegisterSDCRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> RegisterSDCResponse:
    """Register a new foreign SDC in the Foreign Reputation System."""
    frs = FRSClient.get_instance()
    try:
        profile, action = frs.register_sdc(req.sdc_did, req.initial_score)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return RegisterSDCResponse(
        sdc_did=profile.sdc_did,
        sdc_id_hash=profile.sdc_id_hash,
        tier=profile.tier.value,
        score=profile.decayed_score,
    )


# ── GET /diplomacy/sdc/{sdc_did} ─────────────────────────────────────────────

@router.get("/sdc/{sdc_did}")
async def get_sdc_profile(
    sdc_did: str,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> dict:
    """Retrieve a foreign SDC's reputation profile."""
    frs = FRSClient.get_instance()
    try:
        profile, action = frs.get_profile(sdc_did)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"SDC not found: {sdc_did}")

    return profile.model_dump(mode="json")


# ── POST /diplomacy/sdc/transaction ──────────────────────────────────────────

@router.post("/sdc/transaction")
async def record_transaction(
    req: RecordTransactionRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> dict:
    """Record a Valueflows transaction and update an SDC's reputation score."""
    frs = FRSClient.get_instance()
    try:
        profile, action = frs.record_transaction(
            sdc_did=req.sdc_did,
            score_delta=req.score_delta,
            tx_cid=req.tx_cid,
            rationale=req.rationale,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "sdc_did": profile.sdc_did,
        "score": profile.decayed_score,
        "tier": profile.tier.value,
        "tier_name": profile.tier.name,
        "tx_count": profile.tx_count,
    }


# ── POST /diplomacy/sdc/{sdc_did}/quarantine ─────────────────────────────────

@router.post("/sdc/{sdc_did}/quarantine")
async def force_quarantine_sdc(
    sdc_did: str,
    rationale_cid: str,
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> dict:
    """Force-quarantine a foreign SDC (council override)."""
    frs = FRSClient.get_instance()
    try:
        action = frs.force_quarantine(sdc_did, rationale_cid)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"SDC not found: {sdc_did}")

    return {"status": "force_quarantined", "action": action.model_dump()}


# ── DELETE /diplomacy/sdc/{sdc_did}/quarantine ────────────────────────────────

@router.delete("/sdc/{sdc_did}/quarantine")
async def lift_quarantine_sdc(
    sdc_did: str,
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> dict:
    """Lift a force-quarantine on a foreign SDC."""
    frs = FRSClient.get_instance()
    try:
        action = frs.lift_quarantine(sdc_did)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"SDC not found: {sdc_did}")

    return {"status": "quarantine_lifted", "action": action.model_dump()}


# ── POST /diplomacy/ingest ───────────────────────────────────────────────────

@router.post("/ingest", response_model=IngestExternalAssetResponse)
async def ingest_external_asset(
    req: IngestExternalAssetRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> IngestExternalAssetResponse:
    """Ingest an external knowledge asset into the quarantine sandbox."""
    try:
        raw = base64.b64decode(req.data_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 data")

    embassy = IngestionEmbassy.get_instance()
    try:
        asset, action = await embassy.ingest(
            source_sdc_did=req.source_sdc_did,
            original_cid=req.original_cid,
            title=req.title,
            data=raw,
            description=req.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return IngestExternalAssetResponse(
        quarantine_id=str(asset.quarantine_id),
        local_cid=asset.local_cid or "",
        source_tier=asset.source_sdc_tier.value,
        status=asset.status.value,
        collision_count=asset.collision_report.collision_count if asset.collision_report else 0,
    )


# ── GET /diplomacy/sandbox ───────────────────────────────────────────────────

@router.get("/sandbox")
async def list_pending_assets(
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> dict:
    """List all external assets pending review in the quarantine sandbox."""
    embassy = IngestionEmbassy.get_instance()
    pending = embassy.list_pending()
    return {
        "count": len(pending),
        "assets": [a.model_dump(mode="json") for a in pending],
    }


# ── GET /diplomacy/sandbox/{quarantine_id} ───────────────────────────────────

@router.get("/sandbox/{quarantine_id}")
async def get_sandbox_asset(
    quarantine_id: str,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> dict:
    """Retrieve a quarantined asset by ID."""
    embassy = IngestionEmbassy.get_instance()
    try:
        asset = embassy.get_sandbox_asset(quarantine_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Quarantine ID not found: {quarantine_id}")

    return asset.model_dump(mode="json")


# ── POST /diplomacy/sandbox/{quarantine_id}/admit ────────────────────────────

@router.post("/sandbox/{quarantine_id}/admit")
async def admit_asset(
    quarantine_id: str,
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> dict:
    """Admit a quarantined asset — promote to full KnowledgeAsset."""
    embassy = IngestionEmbassy.get_instance()
    try:
        asset, action = await embassy.admit(quarantine_id, author_did=user.did)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Quarantine ID not found: {quarantine_id}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "status": "admitted",
        "promoted_asset_cid": asset.promoted_asset_cid,
        "action": action.model_dump(),
    }


# ── POST /diplomacy/sandbox/{quarantine_id}/reject ──────────────────────────

@router.post("/sandbox/{quarantine_id}/reject")
async def reject_asset(
    quarantine_id: str,
    reason: str = "Does not meet commons standards",
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> dict:
    """Reject a quarantined asset. It remains in the sandbox permanently."""
    embassy = IngestionEmbassy.get_instance()
    try:
        asset, action = embassy.reject(quarantine_id, reason)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Quarantine ID not found: {quarantine_id}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "status": "rejected",
        "local_cid": asset.local_cid,
        "action": action.model_dump(),
    }


# ── POST /diplomacy/research/submit ─────────────────────────────────────────

@router.post("/research/submit", response_model=PeerReviewResponse)
async def submit_for_review(
    req: SubmitForReviewRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> PeerReviewResponse:
    """Submit a knowledge asset for RITL peer review.

    Invokes the PeerReviewGraph with Socratic Cross-Examination.
    If reviewers disagree, the debate escalates to HITL.
    """
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [],
        "agent_id": "ritl-manager-v1",
        "action_log": [],
        "error": None,
        "asset_cid": req.asset_cid,
        "author_did": req.author_did,
        "submission_title": req.title,
        "asset_metadata": None,
        "blind_mode": req.blind_mode,
        "reviewer_assignments": [],
        "reviews": [],
        "socratic_exchanges": [],
        "review_consensus": None,
        "rationale_log": [],
        "escalation_signal": False,
        "requires_human_token": False,
    }

    try:
        peer_review_graph.invoke(initial_state, config=config)
    except Exception as exc:
        logger.error("RITL graph error: %s", exc)
        raise HTTPException(status_code=500, detail=f"RITL graph error: {exc}")

    snapshot = peer_review_graph.get_state(config)
    state = snapshot.values

    if state.get("error"):
        raise HTTPException(status_code=422, detail=state["error"])

    consensus = state.get("review_consensus")
    status = "review_complete" if consensus in ("accept", "reject") else "escalated_to_hitl"

    return PeerReviewResponse(
        thread_id=thread_id,
        submission_id=str(uuid4()),  # STUB: would come from DB
        round_number=1,
        status=status,
        reviews=state.get("reviews", []),
        socratic_log=state.get("socratic_exchanges", []),
        consensus=consensus,
        action_log=state.get("action_log", []),
    )


# ── POST /diplomacy/research/review ─────────────────────────────────────────

@router.post("/research/review", response_model=PeerReviewResponse)
async def review_research(
    thread_id: str,
    approved: bool,
    reason: str = "",
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> PeerReviewResponse:
    """HITL resume endpoint for escalated peer reviews.

    The researcher or StewardshipCouncil approves or rejects the submission
    after reviewing the peer assessment and Socratic transcript.
    """
    config = {"configurable": {"thread_id": thread_id}}

    try:
        snapshot = peer_review_graph.get_state(config)
    except Exception:
        raise HTTPException(
            status_code=404,
            detail=f"No active review found for thread_id: {thread_id}",
        )

    state = snapshot.values
    if not state:
        raise HTTPException(
            status_code=404,
            detail=f"No active review found for thread_id: {thread_id}",
        )

    if not approved:
        return PeerReviewResponse(
            thread_id=thread_id,
            submission_id="",
            round_number=1,
            status="researcher_rejected",
            reviews=state.get("reviews", []),
            socratic_log=state.get("socratic_exchanges", []),
            consensus="reject",
            action_log=state.get("action_log", []),
        )

    # Resume the graph past the HITL breakpoint
    peer_review_graph.update_state(
        config,
        {"requires_human_token": False, "review_consensus": "accept"},
        as_node="human_review_research",
    )
    peer_review_graph.invoke(None, config=config)

    updated = peer_review_graph.get_state(config).values

    return PeerReviewResponse(
        thread_id=thread_id,
        submission_id="",
        round_number=1,
        status="review_complete",
        reviews=updated.get("reviews", []),
        socratic_log=updated.get("socratic_exchanges", []),
        consensus=updated.get("review_consensus", "accept"),
        action_log=updated.get("action_log", []),
    )


# ══════════════════════════════════════════════════════════════════════════════
# CREDENTIAL EMBASSY — W3C VC Verification & Attestation
# ══════════════════════════════════════════════════════════════════════════════

# ── POST /diplomacy/credentials/verify ────────────────────────────────────────

@router.post("/credentials/verify", response_model=VerifyCredentialResponse)
async def verify_credential(
    req: VerifyCredentialRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> VerifyCredentialResponse:
    """Verify a W3C Verifiable Credential against the TrustRegistry.

    Offline-first: does NOT contact the issuer's server.
    Returns verification result without minting an attestation.
    """
    verifier = VCVerifier.get_instance()
    result, action = verifier.verify_vc(req.credential_json)

    return VerifyCredentialResponse(
        valid=result.valid,
        issuer_did=result.issuer_did,
        issuer_name=result.issuer_name,
        key_fingerprint=result.key_fingerprint,
        credential_type=result.credential_type,
        subject_role=result.subject_role,
        subject_institution=result.subject_institution,
        error=result.error,
        warnings=result.warnings,
    )


# ── POST /diplomacy/credentials/ingest ────────────────────────────────────────

@router.post("/credentials/ingest", response_model=IngestCredentialResponse)
async def ingest_credential(
    req: IngestCredentialRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> IngestCredentialResponse:
    """Full credential ingestion: verify VC → mint attestation → pin to Mesh.

    Pipeline:
      1. Verify the VC signature against TrustRegistry (offline).
      2. Strip PII (semantic sanitisation).
      3. Mint a local non-transferable attestation (internal SBT).
      4. Pin sanitised attestation to Mesh Archive as CausalEvent.
      5. Generate ZK-Attestation placeholder.
    """
    embassy = IngestionEmbassy.get_instance()
    try:
        attestation, action = await embassy.ingest_credential(
            req.credential_json, req.holder_did,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return IngestCredentialResponse(
        attestation_id=attestation["attestation_id"],
        holder_did=attestation["holder_did"],
        issuer_did=attestation.get("issuer_did", ""),
        credential_type=attestation.get("credential_type", ""),
        verified_role=attestation.get("verified_role", ""),
        verified_institution=attestation.get("verified_institution", ""),
        mesh_cid=attestation.get("mesh_cid", ""),
        causal_event_cid=attestation.get("causal_event_cid", ""),
        zk_attestation_hash=attestation.get("zk_attestation", {}).get("proof_hash", ""),
        status=attestation.get("status", "Active"),
    )


# ── GET /diplomacy/attestations/{attestation_id} ─────────────────────────────

@router.get("/attestations/{attestation_id}", response_model=AttestationResponse)
async def get_attestation(
    attestation_id: str,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> AttestationResponse:
    """Retrieve an attestation by ID."""
    agent = IdentityAttestationAgent.get_instance()
    try:
        att = agent.get_attestation(attestation_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Attestation not found: {attestation_id}",
        )

    return AttestationResponse(
        attestation_id=att["attestation_id"],
        holder_did=att["holder_did"],
        issuer_did=att.get("issuer_did", ""),
        issuer_name=att.get("issuer_name", ""),
        credential_type=att.get("credential_type", ""),
        verified_role=att.get("verified_role", ""),
        verified_institution=att.get("verified_institution", ""),
        status=att.get("status", ""),
        created_at=att.get("created_at", ""),
        tombstoned_at=att.get("tombstoned_at"),
        mesh_cid=att.get("mesh_cid"),
        causal_event_cid=att.get("causal_event_cid"),
        zk_attestation=att.get("zk_attestation"),
    )


# ── GET /diplomacy/attestations/holder/{holder_did} ──────────────────────────

@router.get("/attestations/holder/{holder_did}")
async def get_attestations_by_holder(
    holder_did: str,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> dict:
    """Retrieve all attestations for a given holder DID."""
    agent = IdentityAttestationAgent.get_instance()
    attestations = agent.get_attestations_by_holder(holder_did)
    return {
        "holder_did": holder_did,
        "count": len(attestations),
        "attestations": attestations,
    }


# ── POST /diplomacy/credentials/revoke-issuer ────────────────────────────────

@router.post("/credentials/revoke-issuer", response_model=RevokeIssuerResponse)
async def revoke_issuer(
    req: RevokeIssuerRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> RevokeIssuerResponse:
    """Revoke an issuer key and tombstone all derived attestations.

    Tombstone propagation: every attestation minted from a credential
    signed by this key is flagged as Tombstoned.
    """
    trust_registry = TrustRegistryClient.get_instance()
    attestation_agent = IdentityAttestationAgent.get_instance()

    # Step 1: Revoke the issuer key in the TrustRegistry
    try:
        revoke_action = trust_registry.revoke_issuer(
            req.key_fingerprint, req.rationale,
        )
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Issuer key not found: {req.key_fingerprint}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Step 2: Tombstone all derived attestations
    tombstoned_ids, tombstone_action = attestation_agent.tombstone_by_issuer_key(
        req.key_fingerprint, req.rationale,
    )

    return RevokeIssuerResponse(
        key_fingerprint=req.key_fingerprint,
        tombstoned_count=len(tombstoned_ids),
        tombstoned_ids=tombstoned_ids,
        rationale=req.rationale,
    )
