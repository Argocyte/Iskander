"""
library_manager.py — Iskander Knowledge Commons (IKC) Library Manager.

Singleton that manages KnowledgeAsset lifecycle against SovereignStorage.
All knowledge content is pinned to IPFS and referenced by CID. Status
changes are metadata-only writes (StatusTag) — the original CID is NEVER
deleted.

TOMBSTONE-ONLY INVARIANT:
    This module contains ZERO calls to any method that removes data from IPFS.
    ``update_status()`` pins a *new* StatusTag JSON blob and updates the asset's
    ``metadata_cid`` field. The original content CID remains permanently pinned.

GLASS BOX:
    Every public method returns an ``AgentAction`` recording what happened and why.

DEPENDENCY GRAPH:
    Assets declare dependencies via ``dependency_manifest``. The LibraryManager
    maintains forward + reverse indexes for O(1) lookup. Cycle detection via DFS
    prevents circular dependency chains. ``check_downstream_impact()`` uses BFS
    with a visited-set to safely traverse even if a cycle somehow exists.

BREAK-GLASS:
    A global flag that, when activated by the StewardshipCouncil, immediately
    halts all curation activity. ``update_status()`` and the curator graph both
    check this flag before proceeding.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.config import settings
from backend.mesh.sovereign_storage import SovereignStorage
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel
from backend.schemas.knowledge import (
    KnowledgeAsset,
    KnowledgeAssetStatus,
    StatusTag,
)

logger = logging.getLogger(__name__)

AGENT_ID = "library-manager-v1"


# ── Valid status transitions ─────────────────────────────────────────────────

VALID_TRANSITIONS: dict[KnowledgeAssetStatus, set[KnowledgeAssetStatus]] = {
    KnowledgeAssetStatus.ACTIVE: {
        KnowledgeAssetStatus.LEGACY,
        KnowledgeAssetStatus.TOMBSTONED,
        KnowledgeAssetStatus.DEEP_FREEZE,
    },
    KnowledgeAssetStatus.LEGACY: {
        KnowledgeAssetStatus.ACTIVE,
        KnowledgeAssetStatus.TOMBSTONED,
    },
    KnowledgeAssetStatus.TOMBSTONED: set(),  # Terminal — no transitions out
    KnowledgeAssetStatus.DEEP_FREEZE: {
        KnowledgeAssetStatus.ACTIVE,  # Only via StewardshipCouncil HITL
    },
}


class LibraryManager:
    """Singleton managing KnowledgeAsset lifecycle against SovereignStorage.

    Obtain via ``LibraryManager.get_instance()``.

    TOMBSTONE-ONLY INVARIANT: This class NEVER calls any method that would
    delete a CID from IPFS. Status changes are metadata-only writes.
    """

    _instance: LibraryManager | None = None

    def __init__(self) -> None:
        self._storage = SovereignStorage.get_instance()
        # In-memory registry: CID → KnowledgeAsset (STUB for DB)
        self._registry: dict[str, KnowledgeAsset] = {}
        # Forward deps: from_cid → set of to_cids (this asset depends on those)
        self._dependencies: dict[str, set[str]] = defaultdict(set)
        # Reverse deps: to_cid → set of from_cids (those assets depend on this)
        self._dependents: dict[str, set[str]] = defaultdict(set)
        # Break-Glass state
        self._break_glass: bool = False
        self._break_glass_last_deactivated: float = 0.0
        self._break_glass_activations_today: int = 0
        self._break_glass_day_start: float = time.time()

    @classmethod
    def get_instance(cls) -> LibraryManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Test-only: tear down the singleton so tests start fresh."""
        cls._instance = None

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════════

    async def register_asset(
        self,
        data: bytes,
        title: str,
        author_did: str,
        description: str | None = None,
        dependency_manifest: list[str] | None = None,
        audience: str = "federation",
    ) -> tuple[KnowledgeAsset, AgentAction]:
        """Pin content to IPFS, create KnowledgeAsset record, register deps.

        Validates:
          - All CIDs in ``dependency_manifest`` exist in the registry.
          - No circular dependency would be introduced.
          - ``ikc_max_dependents_per_asset`` is not exceeded for any dep.

        Returns:
            (asset, agent_action)

        Raises:
            ValueError: If dependency validation fails.
        """
        dep_cids = dependency_manifest or []

        # Validate all dependency CIDs exist
        for dep_cid in dep_cids:
            if dep_cid not in self._registry:
                raise ValueError(
                    f"Dependency CID not found in registry: {dep_cid}"
                )

        # Pin content to IPFS
        content_hash = hashlib.sha256(data).hexdigest()
        cid, replica_count, _pin_action = await self._storage.pin(
            data, audience=audience,
        )

        # Check for cycles BEFORE registering
        for dep_cid in dep_cids:
            if self._detect_cycle(cid, dep_cid):
                raise ValueError(
                    f"Circular dependency detected: {cid} -> {dep_cid} "
                    f"would create a cycle"
                )

        # Check dependents cap
        for dep_cid in dep_cids:
            current_count = len(self._dependents.get(dep_cid, set()))
            if current_count >= settings.ikc_max_dependents_per_asset:
                raise ValueError(
                    f"CID {dep_cid} has reached the maximum dependents limit "
                    f"({settings.ikc_max_dependents_per_asset})"
                )

        # Create asset record
        now = datetime.now(timezone.utc)
        asset = KnowledgeAsset(
            cid=cid,
            author_did=author_did,
            title=title,
            description=description,
            content_hash=content_hash,
            dependency_manifest=dep_cids,
            created_at=now,
            updated_at=now,
        )

        # Register in memory
        self._registry[cid] = asset

        # Register dependency edges
        self._register_dependencies(cid, dep_cids)

        action = AgentAction(
            agent_id=AGENT_ID,
            action="register_knowledge_asset",
            rationale=(
                f"Pinned new knowledge asset '{title}' by {author_did} to "
                f"IPFS (CID: {cid}). Dependencies: {dep_cids or 'none'}. "
                f"Content hash: {content_hash[:16]}..."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "asset_id": str(asset.asset_id),
                "cid": cid,
                "author_did": author_did,
                "title": title,
                "version": asset.version,
                "dependency_count": len(dep_cids),
                "replica_count": replica_count,
            },
        )

        logger.info(
            "Registered knowledge asset: cid=%s title=%s deps=%d",
            cid, title, len(dep_cids),
        )
        return asset, action

    async def get_asset(self, cid: str) -> tuple[KnowledgeAsset, AgentAction]:
        """Retrieve asset metadata by CID.

        Raises:
            KeyError: If CID not found in registry.
        """
        asset = self._registry.get(cid)
        if asset is None:
            raise KeyError(f"Knowledge asset not found: {cid}")

        action = AgentAction(
            agent_id=AGENT_ID,
            action="get_knowledge_asset",
            rationale=f"Retrieved metadata for knowledge asset CID {cid}.",
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"cid": cid, "status": asset.status.value},
        )
        return asset, action

    async def update_status(
        self,
        cid: str,
        new_status: KnowledgeAssetStatus,
        changed_by: str,
        rationale: str,
    ) -> tuple[StatusTag, AgentAction]:
        """Metadata-only status update. Pins a StatusTag to IPFS.

        TOMBSTONE-ONLY: This method NEVER deletes the original CID. It only
        writes a new StatusTag metadata blob and updates the asset's
        ``metadata_cid`` field.

        Raises:
            ValueError: If transition is invalid, break-glass is active,
                        or CID not found.
        """
        if self._break_glass:
            raise ValueError(
                "Break-Glass is active — all curation halted. "
                "Deactivate Break-Glass before making status changes."
            )

        asset = self._registry.get(cid)
        if asset is None:
            raise ValueError(f"Knowledge asset not found: {cid}")

        # Validate transition
        allowed = VALID_TRANSITIONS.get(asset.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid status transition: {asset.status.value} → "
                f"{new_status.value}. Allowed: {[s.value for s in allowed]}"
            )

        # Create StatusTag
        tag = StatusTag(
            asset_cid=cid,
            new_status=new_status,
            previous_status=asset.status,
            changed_by=changed_by,
            rationale=rationale,
        )

        # Pin StatusTag to IPFS (metadata-only — original CID untouched)
        tag_json = json.dumps(tag.model_dump(mode="json")).encode("utf-8")
        metadata_cid, _, _pin_action = await self._storage.pin(
            tag_json, audience="federation",
        )

        # Update asset record (in-memory STUB)
        previous_status = asset.status
        asset.status = new_status
        asset.metadata_cid = metadata_cid
        asset.updated_at = datetime.now(timezone.utc)

        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"update_status:{previous_status.value}->{new_status.value}",
            rationale=(
                f"Status change for asset {cid}: {previous_status.value} → "
                f"{new_status.value}. Reason: {rationale}. StatusTag pinned "
                f"at CID {metadata_cid}. Original content CID preserved "
                f"(tombstone-only invariant)."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "asset_cid": cid,
                "previous_status": previous_status.value,
                "new_status": new_status.value,
                "metadata_cid": metadata_cid,
                "changed_by": changed_by,
            },
        )

        logger.info(
            "Status change: cid=%s %s->%s by=%s",
            cid, previous_status.value, new_status.value, changed_by,
        )
        return tag, action

    async def check_downstream_impact(
        self, cid: str,
    ) -> tuple[list[str], AgentAction]:
        """Return list of ACTIVE asset CIDs that depend on ``cid``.

        Uses BFS on the reverse dependency index with a visited-set to
        prevent infinite loops even if a cycle somehow exists.
        """
        active_dependents: list[str] = []
        visited: set[str] = set()
        queue: deque[str] = deque()

        # Seed with direct dependents
        for dep_cid in self._dependents.get(cid, set()):
            if dep_cid not in visited:
                visited.add(dep_cid)
                queue.append(dep_cid)

        while queue:
            current = queue.popleft()
            asset = self._registry.get(current)
            if asset is not None and asset.status == KnowledgeAssetStatus.ACTIVE:
                active_dependents.append(current)

        action = AgentAction(
            agent_id=AGENT_ID,
            action="check_downstream_impact",
            rationale=(
                f"Checked downstream impact for CID {cid}. "
                f"Found {len(active_dependents)} active dependent(s): "
                f"{active_dependents or 'none'}."
            ),
            ethical_impact=EthicalImpactLevel.LOW,
            payload={
                "target_cid": cid,
                "active_dependents": active_dependents,
                "count": len(active_dependents),
            },
        )
        return active_dependents, action

    # ═══════════════════════════════════════════════════════════════════════════
    # BREAK-GLASS
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def break_glass_active(self) -> bool:
        return self._break_glass

    def activate_break_glass(self) -> AgentAction:
        """Activate Break-Glass — halt all curation activity.

        Enforces cooldown and daily activation limits (VULN-3 mitigation).

        Raises:
            ValueError: If cooldown has not elapsed or daily limit exceeded.
        """
        now = time.time()

        # Reset daily counter if new day
        if now - self._break_glass_day_start > 86400:
            self._break_glass_activations_today = 0
            self._break_glass_day_start = now

        # Check daily limit
        if (
            self._break_glass_activations_today
            >= settings.ikc_break_glass_max_activations_per_day
        ):
            raise ValueError(
                f"Break-Glass daily activation limit exceeded "
                f"({settings.ikc_break_glass_max_activations_per_day}/day). "
                f"Requires multi-steward override."
            )

        # Check cooldown
        elapsed = now - self._break_glass_last_deactivated
        if (
            self._break_glass_last_deactivated > 0
            and elapsed < settings.ikc_break_glass_cooldown_seconds
        ):
            remaining = settings.ikc_break_glass_cooldown_seconds - elapsed
            raise ValueError(
                f"Break-Glass cooldown active — {remaining:.0f}s remaining. "
                f"Cannot re-activate until cooldown expires."
            )

        self._break_glass = True
        self._break_glass_activations_today += 1

        action = AgentAction(
            agent_id=AGENT_ID,
            action="break_glass_activated",
            rationale=(
                "Break-Glass activated by StewardshipCouncil. All curation "
                "activity is now halted. Active debates will enter 'paused' "
                "state. Activation count today: "
                f"{self._break_glass_activations_today}/"
                f"{settings.ikc_break_glass_max_activations_per_day}."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "activations_today": self._break_glass_activations_today,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.warning("BREAK-GLASS ACTIVATED — all curation halted")
        return action

    def deactivate_break_glass(self) -> AgentAction:
        """Deactivate Break-Glass — resume curation activity."""
        self._break_glass = False
        self._break_glass_last_deactivated = time.time()

        action = AgentAction(
            agent_id=AGENT_ID,
            action="break_glass_deactivated",
            rationale=(
                "Break-Glass deactivated. Curation activity may resume. "
                f"Cooldown of {settings.ikc_break_glass_cooldown_seconds}s "
                f"begins now before re-activation is possible."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "cooldown_seconds": settings.ikc_break_glass_cooldown_seconds,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info("Break-Glass deactivated — curation resumed")
        return action

    # ═══════════════════════════════════════════════════════════════════════════
    # DEPENDENCY GRAPH INTERNALS
    # ═══════════════════════════════════════════════════════════════════════════

    def _register_dependencies(
        self, from_cid: str, dep_cids: list[str],
    ) -> None:
        """Add edges to forward + reverse dependency indexes."""
        for to_cid in dep_cids:
            self._dependencies[from_cid].add(to_cid)
            self._dependents[to_cid].add(from_cid)

    def _detect_cycle(self, from_cid: str, to_cid: str) -> bool:
        """DFS from ``to_cid`` following forward edges (_dependencies).

        Returns True if ``from_cid`` is reachable from ``to_cid``,
        meaning adding edge ``from_cid → to_cid`` would create a cycle.
        """
        # Special case: self-reference
        if from_cid == to_cid:
            return True

        visited: set[str] = set()
        stack: list[str] = [to_cid]

        while stack:
            current = stack.pop()
            if current == from_cid:
                return True
            if current in visited:
                continue
            visited.add(current)
            for neighbor in self._dependencies.get(current, set()):
                if neighbor not in visited:
                    stack.append(neighbor)

        return False
