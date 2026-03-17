"""
arbitration_protocol.py — ActivityPub extensions for federated jury selection (Phase 15).

Implements the custom Iskander ActivityPub activity types used by the
Solidarity Court protocol:

  iskander:ArbitrationRequest — Sent to sister coops to request jury volunteers.
  iskander:JuryNomination     — Sister coop responds with a nominated juror.
  iskander:Verdict            — Final verdict broadcast to all parties.

These activities extend the standard ActivityPub vocabulary. Receiving nodes
that do not understand the iskander: namespace will treat them as unknown
activities and ignore them gracefully (per ActivityPub spec §3.1).

PROTOCOL FLOW:
  1. Iskander node sends ArbitrationRequest to 5+ sister coops (ActivityPub outbox).
  2. Sister coops receive it via their inbox, present it to their governance.
  3. Sister coops respond with JuryNomination (1-2 volunteers each).
  4. Receiving node collects nominations until jury_size is met.
  5. Jury is randomly selected deterministically from nominations.
  6. Jury deliberates via Matrix rooms (Phase 14A).
  7. After verdict, the operator Safe records it via ArbitrationRegistry.sol.
  8. Receiving node sends Verdict activity to all parties for transparency.

RANDOMNESS FOR JURY SELECTION:
  Uses block hash + case ID for deterministic pseudo-randomness (same as
  Kleros/Aragon Court). Not cryptographically secure — sufficient for
  cooperative contexts where participants are known and accountable.
  For production: integrate with a VRF oracle.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.config import settings
from backend.federation.outbox_store import OutboxStore

logger = logging.getLogger(__name__)

# ── Iskander AP Context Extension ─────────────────────────────────────────────

ISKANDER_CONTEXT = {
    "iskander": "https://iskander.coop/ns#",
    "iskander:ArbitrationRequest": {
        "@id": "iskander:ArbitrationRequest",
        "@type": "@id",
    },
    "iskander:JuryNomination": {
        "@id": "iskander:JuryNomination",
        "@type": "@id",
    },
    "iskander:Verdict": {
        "@id": "iskander:Verdict",
        "@type": "@id",
    },
    "escrowId":           {"@id": "iskander:escrowId"},
    "caseId":             {"@id": "iskander:caseId"},
    "termsIpfsCid":       {"@id": "iskander:termsIpfsCid"},
    "jurySize":           {"@id": "iskander:jurySize"},
    "jurorDid":           {"@id": "iskander:jurorDid"},
    "verdictOutcome":     {"@id": "iskander:verdictOutcome"},
    "juryIpfsCid":        {"@id": "iskander:juryIpfsCid"},
    "trustSlashBuyer":    {"@id": "iskander:trustSlashBuyer"},
    "trustSlashSeller":   {"@id": "iskander:trustSlashSeller"},
    # Phase 18: IPD Auditing System — inter-node audit federation types.
    "iskander:AuditRequest": {
        "@id": "iskander:AuditRequest",
        "@type": "@id",
    },
    "iskander:AuditResponse": {
        "@id": "iskander:AuditResponse",
        "@type": "@id",
    },
    "iskander:AuditSummary": {
        "@id": "iskander:AuditSummary",
        "@type": "@id",
    },
    "auditType":              {"@id": "iskander:auditType"},
    "targetNode":             {"@id": "iskander:targetNode"},
    "requestingNode":         {"@id": "iskander:requestingNode"},
    "cooperationScore":       {"@id": "iskander:cooperationScore"},
    "outcomeClassification":  {"@id": "iskander:outcomeClassification"},
    "auditRequestId":         {"@id": "iskander:auditRequestId"},
    # Phase 20: Sovereign Personal Node HITL Routing.
    # A member who runs their own Iskander node receives HITL proposals as
    # ActivityPub activities — not via the coop's central UI. The cooperative
    # routes; it does not gatekeep.
    "iskander:HITLProposal": {
        "@id": "iskander:HITLProposal",
        "@type": "@id",
    },
    "iskander:HITLProposalVote": {
        "@id": "iskander:HITLProposalVote",
        "@type": "@id",
    },
    "proposalId":             {"@id": "iskander:proposalId"},
    "proposalType":           {"@id": "iskander:proposalType"},
    "votingDeadline":         {"@id": "iskander:votingDeadline"},
    "callbackInbox":          {"@id": "iskander:callbackInbox"},
    "safeTransactionDraft":   {"@id": "iskander:safeTransactionDraft"},
    "voterDid":               {"@id": "iskander:voterDid"},
    "voteApproved":           {"@id": "iskander:voteApproved"},
}

_AS_CONTEXT = "https://www.w3.org/ns/activitystreams"


class ArbitrationProtocol:
    """
    Serializes and delivers custom ActivityPub activities for the Solidarity Court.

    Usage:
        proto = ArbitrationProtocol()
        await proto.send_arbitration_request(case_id, escrow_id, target_coops)
    """

    def __init__(self) -> None:
        self._domain = settings.activitypub_domain
        self._base = settings.activitypub_base_url.rstrip("/")
        self._outbox = OutboxStore.get_instance()

    def _actor_url(self, handle: str = "coop") -> str:
        return f"{self._base}/federation/actors/{handle}"

    def _activity_url(self) -> str:
        return f"{self._base}/federation/activities/{uuid.uuid4()}"

    # ── ArbitrationRequest ────────────────────────────────────────────────────

    async def send_arbitration_request(
        self,
        case_id: str,
        escrow_id: str,
        terms_ipfs_cid: str,
        dispute_summary: str,
        jury_size: int,
        target_coop_inboxes: list[str],
    ) -> None:
        """
        Broadcast an ArbitrationRequest to sister cooperatives.

        Each receiving coop's inbox processor routes this to their governance
        process to select 1-2 volunteer jurors. They respond with JuryNomination.

        Args:
            case_id:               Internal case UUID.
            escrow_id:             On-chain escrow ID.
            terms_ipfs_cid:        IPFS CID of the trade contract terms.
            dispute_summary:       Plain-language summary (NOT evidence — privacy!).
            jury_size:             Target number of jurors (typically 5).
            target_coop_inboxes:   List of sister coop ActivityPub inbox URLs.
        """
        activity: dict[str, Any] = {
            "@context": [_AS_CONTEXT, ISKANDER_CONTEXT],
            "id": self._activity_url(),
            "type": "iskander:ArbitrationRequest",
            "actor": self._actor_url(),
            "published": datetime.now(timezone.utc).isoformat(),
            "to": target_coop_inboxes,
            "object": {
                "type": "iskander:ArbitrationRequest",
                "caseId": case_id,
                "escrowId": escrow_id,
                "termsIpfsCid": terms_ipfs_cid,
                "summary": dispute_summary[:500],  # Truncated for privacy.
                "jurySize": jury_size,
                "requestingCoop": self._actor_url(),
                "nominationDeadline": (
                    datetime.now(timezone.utc).replace(
                        day=datetime.now(timezone.utc).day + 7
                    ).isoformat()
                ),
            },
        }

        action = await self._outbox.publish(activity, target_inboxes=target_coop_inboxes)
        logger.info(
            "ArbitrationRequest sent for case %s to %d coops: %s",
            case_id, len(target_coop_inboxes), action.action,
        )

    # ── JuryNomination ────────────────────────────────────────────────────────

    async def send_jury_nomination(
        self,
        case_id: str,
        juror_did: str,
        requesting_coop_inbox: str,
    ) -> None:
        """
        Respond to an ArbitrationRequest with a jury volunteer.

        Called by a sister coop's Iskander node after their governance process
        selects a volunteer juror.
        """
        activity: dict[str, Any] = {
            "@context": [_AS_CONTEXT, ISKANDER_CONTEXT],
            "id": self._activity_url(),
            "type": "iskander:JuryNomination",
            "actor": self._actor_url(),
            "published": datetime.now(timezone.utc).isoformat(),
            "to": [requesting_coop_inbox],
            "object": {
                "type": "iskander:JuryNomination",
                "caseId": case_id,
                "jurorDid": juror_did,
                "nominatingCoop": self._actor_url(),
            },
        }

        action = await self._outbox.publish(activity, target_inboxes=[requesting_coop_inbox])
        logger.info("JuryNomination sent for case %s juror %s", case_id, juror_did[:20])

    # ── Verdict Broadcast ─────────────────────────────────────────────────────

    async def broadcast_verdict(
        self,
        case_id: str,
        escrow_id: str,
        outcome: str,
        jury_ipfs_cid: str,
        rationale_summary: str,
        target_inboxes: list[str],
    ) -> None:
        """
        Broadcast the final verdict to all parties and sister coops.

        This is a transparency mechanism: all participants in the federated
        network can verify the verdict is legitimate and traceable to a
        human jury deliberation record stored on IPFS.
        """
        activity: dict[str, Any] = {
            "@context": [_AS_CONTEXT, ISKANDER_CONTEXT],
            "id": self._activity_url(),
            "type": "iskander:Verdict",
            "actor": self._actor_url(),
            "published": datetime.now(timezone.utc).isoformat(),
            "to": target_inboxes,
            "object": {
                "type": "iskander:Verdict",
                "caseId": case_id,
                "escrowId": escrow_id,
                "verdictOutcome": outcome,
                "juryIpfsCid": jury_ipfs_cid,
                "summary": rationale_summary[:500],
            },
        }

        action = await self._outbox.publish(activity, target_inboxes=target_inboxes)
        logger.info("Verdict broadcast for case %s (outcome: %s)", case_id, outcome)

    # ── Jury Selection ────────────────────────────────────────────────────────

    @staticmethod
    def select_jury(
        nominations: list[dict[str, Any]],
        case_id: str,
        jury_size: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Deterministically select jurors from nominations using case_id as seed.

        Deterministic randomness: SHA-256(case_id + nominator_did) per nominee,
        then sort by hash and take the top jury_size entries.

        This ensures all parties can independently verify the jury selection
        was not manipulated — they simply replay the same algorithm.

        Args:
            nominations: List of JuryNomination dicts with 'jurorDid' and 'nominatingCoop'.
            case_id:     Case UUID used as the randomness seed.
            jury_size:   Number of jurors to select.

        Returns:
            Selected jurors (up to jury_size, or all nominations if fewer).
        """
        scored = []
        for nom in nominations:
            seed = f"{case_id}:{nom.get('jurorDid', '')}".encode()
            score = int(hashlib.sha256(seed).hexdigest(), 16)
            scored.append((score, nom))
        scored.sort(key=lambda x: x[0])
        selected = [nom for _, nom in scored[:jury_size]]
        logger.info(
            "Jury selected for case %s: %d/%d nominees → %d jurors",
            case_id, len(nominations), len(nominations), len(selected),
        )
        return selected

    # ── Phase 18: IPD Audit Federation Methods ─────────────────────────────

    async def send_audit_request(
        self,
        request_id: str,
        target_node_did: str,
        audit_type: str,
        target_inbox: str,
    ) -> None:
        """Request an inter-node audit of a trading partner's reputation.

        Sent to a sister cooperative to verify their reputation data.
        Refusing an audit incurs a soft reputation penalty only — no on-chain slash.
        """
        activity: dict[str, Any] = {
            "@context": [_AS_CONTEXT, ISKANDER_CONTEXT],
            "id": self._activity_url(),
            "type": "iskander:AuditRequest",
            "actor": self._actor_url(),
            "published": datetime.now(timezone.utc).isoformat(),
            "to": [target_inbox],
            "object": {
                "type": "iskander:AuditRequest",
                "auditRequestId": request_id,
                "targetNode": target_node_did,
                "requestingNode": self._actor_url(),
                "auditType": audit_type,
            },
        }

        action = await self._outbox.publish(activity, target_inboxes=[target_inbox])
        logger.info("AuditRequest sent: %s → %s (type: %s)", request_id, target_node_did[:20], audit_type)

    async def send_audit_response(
        self,
        request_id: str,
        cooperation_score: float,
        requesting_coop_inbox: str,
    ) -> None:
        """Respond to an inter-node audit request with reputation data."""
        activity: dict[str, Any] = {
            "@context": [_AS_CONTEXT, ISKANDER_CONTEXT],
            "id": self._activity_url(),
            "type": "iskander:AuditResponse",
            "actor": self._actor_url(),
            "published": datetime.now(timezone.utc).isoformat(),
            "to": [requesting_coop_inbox],
            "object": {
                "type": "iskander:AuditResponse",
                "auditRequestId": request_id,
                "respondingNode": self._actor_url(),
                "cooperationScore": cooperation_score,
            },
        }

        action = await self._outbox.publish(activity, target_inboxes=[requesting_coop_inbox])
        logger.info("AuditResponse sent for request %s (score: %.2f)", request_id, cooperation_score)

    async def broadcast_audit_summary(
        self,
        escrow_id: str,
        outcome_classification: dict[str, str],
        cooperation_score: float,
        target_inboxes: list[str],
    ) -> None:
        """Broadcast post-trade audit summary to federated sister cooperatives.

        Non-confidential: escrow_id, outcome classification, updated cooperation
        score, timestamp. Published for network-wide transparency.
        """
        activity: dict[str, Any] = {
            "@context": [_AS_CONTEXT, ISKANDER_CONTEXT],
            "id": self._activity_url(),
            "type": "iskander:AuditSummary",
            "actor": self._actor_url(),
            "published": datetime.now(timezone.utc).isoformat(),
            "to": target_inboxes,
            "object": {
                "type": "iskander:AuditSummary",
                "escrowId": escrow_id,
                "outcomeClassification": outcome_classification,
                "cooperationScore": cooperation_score,
            },
        }

        action = await self._outbox.publish(activity, target_inboxes=target_inboxes)
        logger.info("AuditSummary broadcast for escrow %s (score: %.2f)", escrow_id, cooperation_score)
