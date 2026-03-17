"""
outbox_store.py — ActivityPub outbound activity persistence (Phase 14B).

Manages the cooperative's public outbox: stores outbound activities in
Postgres (federation_outbox table) and delivers them to remote inboxes
via signed HTTP POST.

DELIVERY FLOW:
  1. Agent produces an activity (Create/Note, Announce, etc.)
  2. Caller invokes OutboxStore.publish(activity, target_inboxes)
  3. Activity is persisted to federation_outbox with delivered=False
  4. Delivery task attempts signed POST to each target inbox
  5. On success: marks delivered=True
  6. On failure: logs the error; retry is out of scope (add a queue for prod)

SIGNING:
  Uses HTTPSignatureSigner with the node's RSA private key loaded from
  settings.activitypub_private_key_pem (env var, never hardcoded).

STUB NOTICE:
  Postgres persistence is stubbed (in-memory list). Replace with asyncpg.
  Key loading returns an empty key in stub mode — sign() produces unsigned headers.

GLASS BOX:
  Every publish() call returns an AgentAction.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.config import settings
from backend.federation.http_signatures import HTTPSignatureSigner
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "federation-outbox"


class OutboxStore:
    """
    Persists and delivers outbound ActivityPub activities.

    Singleton: obtain via OutboxStore.get_instance().
    """

    _instance: "OutboxStore | None" = None

    def __init__(self) -> None:
        # STUB: in-memory store. Replace with asyncpg pool in production.
        self._outbox: list[dict[str, Any]] = []
        self._signer: HTTPSignatureSigner | None = None
        self._init_signer()

    @classmethod
    def get_instance(cls) -> "OutboxStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_signer(self) -> None:
        """Load the node's private key and initialise the HTTP signer."""
        private_key_pem = getattr(settings, "activitypub_private_key_pem", "")
        domain = settings.activitypub_domain
        key_id = f"https://{domain}/federation/actors/coop#main-key"
        self._signer = HTTPSignatureSigner(
            private_key_pem=private_key_pem,
            key_id=key_id,
        )

    # ── Publish ───────────────────────────────────────────────────────────────

    async def publish(
        self,
        activity: dict[str, Any],
        target_inboxes: list[str],
    ) -> AgentAction:
        """
        Persist an outbound activity and deliver it to target inboxes.

        Args:
            activity:       Complete ActivityPub activity object (with @context, id, etc.).
            target_inboxes: List of remote inbox URLs to POST to.

        Returns:
            AgentAction with delivery results.
        """
        # Ensure activity has an id.
        if not activity.get("id"):
            domain = settings.activitypub_domain
            activity["id"] = f"https://{domain}/federation/activities/{uuid.uuid4()}"
        if not activity.get("published"):
            activity["published"] = datetime.now(timezone.utc).isoformat()

        # Persist to outbox (stub: in-memory).
        record = {
            "activity_id": activity["id"],
            "activity_type": activity.get("type", "Unknown"),
            "raw_activity": activity,
            "delivered": False,
            "created_at": activity["published"],
        }
        self._outbox.append(record)
        logger.info("Outbox: stored activity %s", activity["id"])

        # Deliver to each target inbox.
        results: dict[str, bool] = {}
        body_bytes = json.dumps(activity).encode()

        for inbox_url in target_inboxes:
            success = await self._deliver(inbox_url, body_bytes)
            results[inbox_url] = success

        if all(results.values()):
            record["delivered"] = True

        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"publish({activity.get('type', '?')})",
            rationale=(
                "Outbound ActivityPub activity published to federated sister cooperatives. "
                "CCIN Principle 6: Cooperation Among Cooperatives."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "activity_id": activity["id"],
                "type": activity.get("type"),
                "targets": len(target_inboxes),
                "delivered": sum(results.values()),
                "results": results,
            },
        )
        return action

    async def _deliver(self, inbox_url: str, body: bytes) -> bool:
        """
        POST a signed activity to a single remote inbox.

        Returns True on HTTP 2xx, False otherwise.
        """
        if not self._signer:
            logger.warning("No signer configured — skipping delivery to %s", inbox_url)
            return False

        sig_headers = self._signer.sign(method="POST", url=inbox_url, body=body)
        headers = {
            "Content-Type": "application/activity+json",
            "Accept": "application/activity+json",
            **sig_headers,
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(inbox_url, content=body, headers=headers)
                success = 200 <= resp.status_code < 300
                logger.info(
                    "Outbox delivery %s → %s: HTTP %d",
                    "OK" if success else "FAILED",
                    inbox_url,
                    resp.status_code,
                )
                return success
        except Exception as exc:
            logger.error("Outbox delivery to %s failed: %s", inbox_url, exc)
            return False

    # ── Outbox query ──────────────────────────────────────────────────────────

    def get_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        Return the most recent outbound activities.

        Used by GET /federation/actors/{handle}/outbox to return the
        cooperative's public activity stream.
        """
        return sorted(
            self._outbox,
            key=lambda r: r.get("created_at", ""),
            reverse=True,
        )[:limit]

    def total_count(self) -> int:
        return len(self._outbox)
