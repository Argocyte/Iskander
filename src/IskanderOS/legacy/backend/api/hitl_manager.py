"""
hitl_manager.py — Sovereign Personal Node HITL Routing Manager (Phase 20).

Central router for Human-in-the-Loop approval requests. When any Iskander
agent reaches a HITL breakpoint (multi-sig proposal, treasury payment,
contribution review, arbitration verdict, IPD cooperation flag), the manager
determines WHERE to deliver the notification based on the target member's
Decentralized Identifier (DID) document:

ROUTING LOGIC:
  1. Resolve the member's DID via DIDResolver.
  2. If the DID document declares an ActivityPubInbox service endpoint:
       → The member runs their own personal Iskander node.
       → Format the proposal as an iskander:HITLProposal ActivityPub activity.
       → Deliver via OutboxStore (signed HTTP POST to member's personal inbox).
       → The member's PERSONAL AI summarises the vote for them.
  3. Else (fallback):
       → Store the notification locally (hitl_notifications table).
       → Broadcast via WebSocket event bus + Matrix bridge.
       → The member reviews via the cooperative's central Streamlit UI.

This ensures maximum user sovereignty, allowing members to manage multi-coop
memberships from a single personal AI dashboard. A member who runs a
"Single-Member Iskander" at home should never be forced to log into a central
cooperative server to participate in governance.

The cooperative routes notifications — it does not gatekeep. The architecture
bends to support personal self-hosting. The individual human member is the
ultimate authority, not the cooperative.

STUB NOTICE:
  Local notification persistence is in-memory (list). Replace with asyncpg
  for the hitl_notifications table in production.

GLASS BOX:
  Every routing decision produces an AgentAction.
  ActivityPub path → EthicalImpactLevel.HIGH (cross-node communication).
  Local DB path    → EthicalImpactLevel.MEDIUM (internal notification).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.config import settings
from backend.federation.arbitration_protocol import ISKANDER_CONTEXT
from backend.federation.did_resolver import DIDResolver
from backend.federation.outbox_store import OutboxStore
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel
from backend.schemas.hitl import (
    HITLNotification,
    HITLProposal,
    HITLRoutingResult,
)

logger = logging.getLogger(__name__)

AGENT_ID = "hitl-routing-manager"
_AS_CONTEXT = "https://www.w3.org/ns/activitystreams"


class HITLRoutingManager:
    """
    Routes HITL approval requests to members based on DID resolution.

    Singleton: obtain via HITLRoutingManager.get_instance().

    The manager does not decide FOR the member — it decides WHERE to
    deliver the question. If the member runs their own node, they get
    the proposal there. If not, they get it on the coop's UI. The member
    chooses; the cooperative complies.
    """

    _instance: "HITLRoutingManager | None" = None

    def __init__(self) -> None:
        self._outbox = OutboxStore.get_instance()
        self._resolver = DIDResolver.get_instance()
        self._domain = settings.activitypub_domain
        self._base = settings.activitypub_base_url.rstrip("/")

        # STUB: in-memory notification store. Replace with asyncpg pool
        # reading/writing the hitl_notifications table.
        self._notifications: list[HITLNotification] = []

    @classmethod
    def get_instance(cls) -> "HITLRoutingManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Primary Entry Point ────────────────────────────────────────────────────

    async def route_hitl_proposal(
        self,
        member_did: str,
        proposal: HITLProposal,
    ) -> HITLRoutingResult:
        """
        Route a HITL approval request to the appropriate channel for a member.

        This is the single entry point called by any agent graph that reaches
        a HITL breakpoint and needs a specific member's signature or vote.

        Args:
            member_did: The DID of the member who must approve/reject.
            proposal:   The full HITL proposal payload.

        Returns:
            HITLRoutingResult with delivery outcome and Glass Box action.
        """
        # Step 1: Resolve the member's DID to discover their preferred endpoint.
        doc, resolve_action = await self._resolver.resolve_did(member_did)

        # Step 2: Check for ActivityPub inbox service.
        inbox_url: str | None = None
        if doc is not None:
            inbox_url = DIDResolver.get_activitypub_inbox(doc)

        # Step 3: Route.
        if inbox_url:
            return await self._route_activitypub(member_did, proposal, inbox_url)
        else:
            return await self._route_local_db(member_did, proposal)

    # ── ActivityPub Path ───────────────────────────────────────────────────────

    async def _route_activitypub(
        self,
        member_did: str,
        proposal: HITLProposal,
        inbox_url: str,
    ) -> HITLRoutingResult:
        """
        Deliver a HITL proposal to the member's personal Iskander node
        via ActivityPub Server-to-Server protocol.

        The member's personal AI will receive this activity, summarise the
        vote, and present it in their own dashboard. When the member votes,
        their node sends an iskander:HITLProposalVote back to our inbox.

        Radical decentralisation: the member never needs to visit the coop's
        UI. They manage multi-coop memberships from a single personal node.
        """
        activity = self._build_hitl_activity(proposal, inbox_url)
        outbox_action = await self._outbox.publish(activity, target_inboxes=[inbox_url])

        delivery_success = outbox_action.payload.get("delivered", 0) > 0 if outbox_action.payload else False

        # Record in local store for audit trail (both paths get a row).
        notification = HITLNotification(
            id=str(uuid.uuid4()),
            member_did=member_did,
            proposal=proposal,
            route="activitypub",
            status="pending",
        )
        self._notifications.append(notification)

        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"route_hitl(activitypub, {proposal.proposal_type})",
            rationale=(
                f"HITL proposal '{proposal.proposal_id}' routed to member's personal "
                f"Iskander node at {inbox_url} via ActivityPub S2S. The member is "
                f"sovereign — they review proposals on their own infrastructure, not "
                f"the cooperative's centralised UI. Their personal AI will summarise "
                f"the vote. Maximum user sovereignty: manage multi-coop memberships "
                f"from a single personal AI dashboard."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "proposal_id": proposal.proposal_id,
                "proposal_type": proposal.proposal_type,
                "member_did": member_did,
                "route": "activitypub",
                "inbox_url": inbox_url,
                "delivery_success": delivery_success,
                "activity_id": activity.get("id"),
            },
        )

        logger.info(
            "HITL routed via ActivityPub: proposal=%s member=%s inbox=%s success=%s",
            proposal.proposal_id, member_did[:30], inbox_url, delivery_success,
        )

        return HITLRoutingResult(
            route="activitypub",
            proposal_id=proposal.proposal_id,
            member_did=member_did,
            delivery_success=delivery_success,
            agent_action=action,
        )

    # ── Local DB Fallback Path ─────────────────────────────────────────────────

    async def _route_local_db(
        self,
        member_did: str,
        proposal: HITLProposal,
    ) -> HITLRoutingResult:
        """
        Store a HITL proposal locally for Streamlit UI pickup.

        This is the fallback path when the member's DID does not resolve
        to a personal ActivityPub inbox. The notification is stored in the
        hitl_notifications table and broadcast via WebSocket + Matrix.

        The member will review via the cooperative's central Iskander Client
        (Streamlit dashboard) or Matrix room. Not as sovereign as the AP path,
        but still functional.
        """
        notification = HITLNotification(
            id=str(uuid.uuid4()),
            member_did=member_did,
            proposal=proposal,
            route="local_db",
            status="pending",
        )
        self._notifications.append(notification)

        # Broadcast via WebSocket event bus for real-time UI updates.
        try:
            from backend.api.websocket_notifier import WebSocketNotifier
            notifier = WebSocketNotifier.get_instance()
            await notifier.broadcast({
                "task_id": None,
                "agent_id": proposal.agent_id,
                "event": "hitl_required",
                "node": "human_review",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "proposal_id": proposal.proposal_id,
                    "proposal_type": proposal.proposal_type,
                    "thread_id": proposal.thread_id,
                    "member_did": member_did,
                    "summary": proposal.summary,
                },
            })
        except Exception as ws_exc:
            logger.warning("WebSocket broadcast failed for HITL notification: %s", ws_exc)

        # Notify via Matrix bridge for members who monitor governance rooms.
        try:
            from backend.matrix.bridge import AgentBridge
            bridge = AgentBridge.get_instance()
            await bridge.notify_hitl_required(
                agent_id=proposal.agent_id,
                proposal_summary=proposal.summary,
                proposal_id=proposal.proposal_id,
            )
        except Exception as mx_exc:
            logger.warning("Matrix HITL notification failed: %s", mx_exc)

        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"route_hitl(local_db, {proposal.proposal_type})",
            rationale=(
                f"HITL proposal '{proposal.proposal_id}' stored locally — member DID "
                f"'{member_did[:30]}' does not resolve to a personal Iskander node. "
                f"Notification delivered via WebSocket event bus and Matrix governance "
                f"room. The member will review via the cooperative's Streamlit dashboard "
                f"or Matrix. When the member is ready to run their own node, they can "
                f"add an ActivityPubInbox service to their DID document and future "
                f"proposals will route there automatically."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "proposal_id": proposal.proposal_id,
                "proposal_type": proposal.proposal_type,
                "member_did": member_did,
                "route": "local_db",
                "notification_id": notification.id,
            },
        )

        logger.info(
            "HITL routed locally: proposal=%s member=%s (no AP inbox found)",
            proposal.proposal_id, member_did[:30],
        )

        return HITLRoutingResult(
            route="local_db",
            proposal_id=proposal.proposal_id,
            member_did=member_did,
            delivery_success=True,  # Local write always succeeds (in stub).
            agent_action=action,
        )

    # ── ActivityPub Activity Builder ───────────────────────────────────────────

    def _build_hitl_activity(
        self,
        proposal: HITLProposal,
        target_inbox: str,
    ) -> dict[str, Any]:
        """
        Construct an iskander:HITLProposal ActivityPub activity.

        This activity is delivered to the member's personal Iskander node.
        Their node's inbox processor will parse it, and their personal AI
        will summarise the proposal for the member to vote on.

        The callbackInbox field tells the member's node where to POST
        the iskander:HITLProposalVote response.
        """
        return {
            "@context": [_AS_CONTEXT, ISKANDER_CONTEXT],
            "id": f"{self._base}/federation/activities/{uuid.uuid4()}",
            "type": "iskander:HITLProposal",
            "actor": f"{self._base}/federation/actors/coop",
            "published": datetime.now(timezone.utc).isoformat(),
            "to": [target_inbox],
            "object": {
                "type": "iskander:HITLProposal",
                "proposalId": proposal.proposal_id,
                "proposalType": proposal.proposal_type,
                "summary": proposal.summary[:500],
                "safeTransactionDraft": proposal.safe_transaction_draft,
                "votingDeadline": (
                    proposal.voting_deadline.isoformat()
                    if proposal.voting_deadline else None
                ),
                "callbackInbox": proposal.callback_inbox,
                "threadId": proposal.thread_id,
                "agentId": proposal.agent_id,
            },
        }

    # ── Notification Queries ───────────────────────────────────────────────────

    def get_pending_notifications(
        self,
        member_did: str | None = None,
    ) -> list[HITLNotification]:
        """
        Return pending HITL notifications, optionally filtered by member.

        Used by the Streamlit UI to display outstanding approval requests.
        In production, this reads from the hitl_notifications Postgres table.
        """
        results = [
            n for n in self._notifications
            if n.status == "pending"
            and (member_did is None or n.member_did == member_did)
        ]
        return sorted(results, key=lambda n: n.created_at, reverse=True)

    def mark_notification_responded(
        self,
        proposal_id: str,
        approved: bool,
    ) -> bool:
        """
        Update a notification's status after the member votes.

        Called by the governance vote endpoint (Streamlit path) or by the
        inbox processor (ActivityPub path) after processing an inbound
        iskander:HITLProposalVote.

        Returns True if the notification was found and updated, False otherwise.
        """
        for notification in self._notifications:
            if notification.proposal.proposal_id == proposal_id:
                notification.status = "approved" if approved else "rejected"
                notification.responded_at = datetime.now(timezone.utc)
                logger.info(
                    "HITL notification %s marked as %s",
                    proposal_id, notification.status,
                )
                return True
        logger.warning("HITL notification not found for proposal_id=%s", proposal_id)
        return False
