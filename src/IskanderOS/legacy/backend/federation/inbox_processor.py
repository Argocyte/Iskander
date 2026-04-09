"""
inbox_processor.py — ActivityPub inbox activity router (Phase 14B).

Processes inbound ActivityPub activities by type. Called from the
federation router's POST /actors/{handle}/inbox and /inbox endpoints
after HTTP Signature verification.

SUPPORTED ACTIVITY TYPES:
  Follow          — Add sender to the local handle's followers list.
  Accept(Follow)  — Record that a remote actor accepted our Follow.
  Announce        — Reshare: persist to the local activity stream.
  Create(Note)    — Store an inbound Note in the federation_inbox table.
  Undo(Follow)    — Remove the sender from followers.

ISKANDER-SPECIFIC TYPES:
  iskander:ArbitrationRequest — Phase 15: inbound dispute from a sister coop.
  iskander:JuryNomination     — Phase 15: jury volunteer from a sister coop.
  iskander:Verdict            — Phase 15: verdict from the federated jury.
  iskander:AuditRequest       — Phase 18: inter-node audit request.
  iskander:AuditResponse      — Phase 18: audit response with cooperation score.
  iskander:AuditSummary       — Phase 18: post-trade audit summary broadcast.
  iskander:HITLProposalVote   — Phase 20: inbound vote from a member's personal node.

STUB NOTICE:
  Postgres persistence is stubbed (log + return). Replace _persist_activity()
  with asyncpg INSERT calls into federation_inbox.

GLASS BOX:
  Every processed activity produces an AgentAction record that callers
  append to the audit log.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "federation-inbox"


class InboxProcessor:
    """
    Routes inbound ActivityPub activities to type-specific handlers.

    Usage:
        processor = InboxProcessor()
        action = await processor.process(activity, local_handle)
    """

    async def process(
        self,
        activity: dict[str, Any],
        local_handle: str,
    ) -> AgentAction:
        """
        Dispatch an inbound activity to its handler.

        Args:
            activity:     The parsed ActivityPub activity object.
            local_handle: The local actor (handle) the activity was sent to.

        Returns:
            AgentAction recording what was done with the activity.
        """
        activity_type = activity.get("type", "Unknown")
        actor_iri = activity.get("actor", "unknown")
        activity_id = activity.get("id", "")

        logger.info(
            "Inbox[%s]: processing %s from %s", local_handle, activity_type, actor_iri
        )

        handler = {
            "Follow":   self._handle_follow,
            "Accept":   self._handle_accept,
            "Announce": self._handle_announce,
            "Create":   self._handle_create,
            "Undo":     self._handle_undo,
            # Iskander-specific types (Phase 15)
            "iskander:ArbitrationRequest": self._handle_arbitration_request,
            "iskander:JuryNomination":     self._handle_jury_nomination,
            "iskander:Verdict":            self._handle_verdict,
            # Iskander-specific types (Phase 18: IPD Auditing)
            "iskander:AuditRequest":       self._handle_audit_request,
            "iskander:AuditResponse":      self._handle_audit_response,
            "iskander:AuditSummary":       self._handle_audit_summary,
            # Iskander-specific types (Phase 20: Sovereign Personal Node HITL)
            "iskander:HITLProposalVote":   self._handle_hitl_vote,
        }.get(activity_type, self._handle_unknown)

        return await handler(activity, local_handle)

    # ── Follow ─────────────────────────────────────────────────────────────────

    async def _handle_follow(
        self, activity: dict[str, Any], local_handle: str
    ) -> AgentAction:
        """
        Record an incoming Follow request.

        In production: INSERT into federation_followers, then send Accept
        activity back to the follower via the Outbox.
        """
        actor_iri = activity.get("actor", "")

        # STUB: log follow; real impl persists to federation_followers table.
        await self._persist_activity(activity, processed=False)
        logger.info("Follow request from %s for @%s", actor_iri, local_handle)

        return AgentAction(
            agent_id=AGENT_ID,
            action=f"Follow accepted: {actor_iri} → @{local_handle}",
            rationale=(
                "Inbound Follow request from federated coop node. "
                "Auto-accepting per open federation policy (ICA Principle 6)."
            ),
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"actor": actor_iri, "local_handle": local_handle},
        )

    # ── Accept ────────────────────────────────────────────────────────────────

    async def _handle_accept(
        self, activity: dict[str, Any], local_handle: str
    ) -> AgentAction:
        """Record that a remote actor accepted our Follow request."""
        actor_iri = activity.get("actor", "")
        await self._persist_activity(activity, processed=True)

        return AgentAction(
            agent_id=AGENT_ID,
            action=f"Follow accepted by {actor_iri}",
            rationale="Remote cooperative accepted our Follow — federation link established.",
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"actor": actor_iri},
        )

    # ── Announce ──────────────────────────────────────────────────────────────

    async def _handle_announce(
        self, activity: dict[str, Any], local_handle: str
    ) -> AgentAction:
        """Reshare: persist to the local activity stream for display."""
        actor_iri = activity.get("actor", "")
        obj = activity.get("object", {})
        await self._persist_activity(activity, processed=True)

        return AgentAction(
            agent_id=AGENT_ID,
            action=f"Announce received from {actor_iri}",
            rationale="Sister coop broadcast — stored for cooperative information sharing.",
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"actor": actor_iri, "object_type": obj.get("type") if isinstance(obj, dict) else "IRI"},
        )

    # ── Create ────────────────────────────────────────────────────────────────

    async def _handle_create(
        self, activity: dict[str, Any], local_handle: str
    ) -> AgentAction:
        """
        Store an inbound Note or other object.

        For Create(Note) activities, the note content is persisted to
        federation_inbox for display in the cooperative's activity feed.
        """
        actor_iri = activity.get("actor", "")
        obj = activity.get("object", {})
        obj_type = obj.get("type", "Unknown") if isinstance(obj, dict) else "IRI"
        await self._persist_activity(activity, processed=True)

        return AgentAction(
            agent_id=AGENT_ID,
            action=f"Create({obj_type}) received from {actor_iri}",
            rationale="Inbound federated content stored in local activity stream.",
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"actor": actor_iri, "object_type": obj_type},
        )

    # ── Undo ──────────────────────────────────────────────────────────────────

    async def _handle_undo(
        self, activity: dict[str, Any], local_handle: str
    ) -> AgentAction:
        """Remove a Follow (or other undoable activity) from local records."""
        actor_iri = activity.get("actor", "")
        obj = activity.get("object", {})
        obj_type = obj.get("type", "Unknown") if isinstance(obj, dict) else "Undo"
        await self._persist_activity(activity, processed=True)

        return AgentAction(
            agent_id=AGENT_ID,
            action=f"Undo({obj_type}) from {actor_iri}",
            rationale="Federated actor undid a previous action — local records updated.",
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"actor": actor_iri, "undone_type": obj_type},
        )

    # ── Iskander Phase 15 types (stubs) ────────────────────────────────────────

    async def _handle_arbitration_request(
        self, activity: dict[str, Any], local_handle: str
    ) -> AgentAction:
        """Phase 15 stub: inbound arbitration request from a sister coop."""
        await self._persist_activity(activity, processed=False)
        return AgentAction(
            agent_id=AGENT_ID,
            action="iskander:ArbitrationRequest received",
            rationale="Inbound arbitration request stored — Phase 15 handler not yet active.",
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={"activity_id": activity.get("id"), "actor": activity.get("actor")},
        )

    async def _handle_jury_nomination(
        self, activity: dict[str, Any], local_handle: str
    ) -> AgentAction:
        """Phase 15 stub: jury volunteer from a sister coop."""
        await self._persist_activity(activity, processed=False)
        return AgentAction(
            agent_id=AGENT_ID,
            action="iskander:JuryNomination received",
            rationale="Jury nomination stored — Phase 15 handler not yet active.",
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={"activity_id": activity.get("id"), "actor": activity.get("actor")},
        )

    async def _handle_verdict(
        self, activity: dict[str, Any], local_handle: str
    ) -> AgentAction:
        """Phase 15 stub: verdict from the federated jury."""
        await self._persist_activity(activity, processed=False)
        return AgentAction(
            agent_id=AGENT_ID,
            action="iskander:Verdict received",
            rationale="Federated jury verdict stored — Phase 15 handler not yet active.",
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={"activity_id": activity.get("id"), "actor": activity.get("actor")},
        )

    # ── Iskander Phase 18 types (IPD Auditing) ──────────────────────────────

    async def _handle_audit_request(
        self, activity: dict[str, Any], local_handle: str
    ) -> AgentAction:
        """Phase 18: inbound audit request from a sister coop.

        A sister cooperative is requesting verification of reputation data.
        Refusing incurs a soft reputation penalty (audit_compliance_rate deduction)
        but never an on-chain trust slash.
        """
        await self._persist_activity(activity, processed=False)
        obj = activity.get("object", {})
        return AgentAction(
            agent_id=AGENT_ID,
            action="iskander:AuditRequest received",
            rationale=(
                "Inter-node audit request stored. The cooperative's governance process "
                "will decide whether to comply. Refusing incurs only a soft reputation "
                "penalty — no on-chain trust slash."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "activity_id": activity.get("id"),
                "actor": activity.get("actor"),
                "audit_type": obj.get("auditType") if isinstance(obj, dict) else None,
                "request_id": obj.get("auditRequestId") if isinstance(obj, dict) else None,
            },
        )

    async def _handle_audit_response(
        self, activity: dict[str, Any], local_handle: str
    ) -> AgentAction:
        """Phase 18: response to our audit request from a sister coop."""
        await self._persist_activity(activity, processed=False)
        obj = activity.get("object", {})
        return AgentAction(
            agent_id=AGENT_ID,
            action="iskander:AuditResponse received",
            rationale=(
                "Audit response stored. The cooperation score from the audited node "
                "will be incorporated into the IPD reputation graph."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "activity_id": activity.get("id"),
                "actor": activity.get("actor"),
                "request_id": obj.get("auditRequestId") if isinstance(obj, dict) else None,
                "cooperation_score": obj.get("cooperationScore") if isinstance(obj, dict) else None,
            },
        )

    async def _handle_audit_summary(
        self, activity: dict[str, Any], local_handle: str
    ) -> AgentAction:
        """Phase 18: post-trade audit summary broadcast from a sister coop."""
        await self._persist_activity(activity, processed=True)
        obj = activity.get("object", {})
        return AgentAction(
            agent_id=AGENT_ID,
            action="iskander:AuditSummary received",
            rationale=(
                "Post-trade audit summary from federated network stored. Contains "
                "non-confidential outcome classification and cooperation score update. "
                "Used to maintain network-wide reputation awareness."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "activity_id": activity.get("id"),
                "actor": activity.get("actor"),
                "escrow_id": obj.get("escrowId") if isinstance(obj, dict) else None,
                "cooperation_score": obj.get("cooperationScore") if isinstance(obj, dict) else None,
            },
        )

    # ── Iskander Phase 20: Sovereign HITL Vote ──────────────────────────────

    async def _handle_hitl_vote(
        self, activity: dict[str, Any], local_handle: str
    ) -> AgentAction:
        """Phase 20: inbound HITL vote from a member's personal Iskander node.

        When a member runs their own single-member Iskander node, HITL proposals
        are pushed to their personal inbox as iskander:HITLProposal activities.
        Their personal AI summarises the vote, and the member decides. This
        handler receives their response.

        The member exercised their sovereign right to review and vote on their
        own infrastructure. The cooperative now resumes the agent graph.

        PRODUCTION INTEGRATION:
            After persisting, this handler should:
            1. Call HITLRoutingManager.mark_notification_responded(proposal_id, approved)
            2. Resume the LangGraph graph at the correct checkpoint:
               governance_graph.update_state(config, {"hitl_approved": approved}, as_node="human_review")
               governance_graph.invoke(None, config=config)
            This is stubbed: only logs and persists. Graph resumption requires
            mapping proposal_type → correct graph instance, which is deferred.
        """
        await self._persist_activity(activity, processed=False)
        obj = activity.get("object", {}) if isinstance(activity.get("object"), dict) else {}
        actor_iri = activity.get("actor", "unknown")

        proposal_id = obj.get("proposalId", "")
        voter_did = obj.get("voterDid", "")
        vote_approved = obj.get("voteApproved", False)
        thread_id = obj.get("threadId", "")

        # STUB: Mark notification as responded in the routing manager.
        try:
            from backend.api.hitl_manager import HITLRoutingManager
            manager = HITLRoutingManager.get_instance()
            manager.mark_notification_responded(proposal_id, vote_approved)
        except Exception as mgr_exc:
            logger.warning("Failed to update HITL notification status: %s", mgr_exc)

        logger.info(
            "HITL vote received: proposal=%s voter=%s approved=%s thread=%s",
            proposal_id, voter_did[:30], vote_approved, thread_id,
        )

        return AgentAction(
            agent_id=AGENT_ID,
            action=f"iskander:HITLProposalVote received (proposal={proposal_id[:20]})",
            rationale=(
                f"Inbound HITL vote from member's personal Iskander node ({actor_iri}). "
                f"The member exercised their sovereign right to review and vote on "
                f"their own infrastructure — not the cooperative's central UI. "
                f"Vote: {'APPROVED' if vote_approved else 'REJECTED'}. "
                f"The cooperative respects the member's decision and will resume "
                f"the agent graph at thread_id={thread_id[:20]}."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "activity_id": activity.get("id"),
                "actor": actor_iri,
                "proposal_id": proposal_id,
                "voter_did": voter_did,
                "vote_approved": vote_approved,
                "thread_id": thread_id,
            },
        )

    # ── Unknown ───────────────────────────────────────────────────────────────

    async def _handle_unknown(
        self, activity: dict[str, Any], local_handle: str
    ) -> AgentAction:
        activity_type = activity.get("type", "Unknown")
        await self._persist_activity(activity, processed=False)
        logger.info("Unhandled activity type: %s", activity_type)

        return AgentAction(
            agent_id=AGENT_ID,
            action=f"Unknown activity type '{activity_type}' — stored unprocessed.",
            rationale="Unrecognised ActivityPub type stored for manual review.",
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"type": activity_type, "actor": activity.get("actor")},
        )

    # ── Persistence stub ──────────────────────────────────────────────────────

    async def _persist_activity(
        self, activity: dict[str, Any], processed: bool
    ) -> None:
        """
        Persist an inbound activity to the federation_inbox table.

        STUB: logs the activity_id. Replace with asyncpg INSERT:
            INSERT INTO federation_inbox
              (activity_id, activity_type, actor_iri, raw_activity, processed)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (activity_id) DO NOTHING
        """
        logger.debug(
            "federation_inbox: %s from %s (processed=%s)",
            activity.get("id", "?"),
            activity.get("actor", "?"),
            processed,
        )
