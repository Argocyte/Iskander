"""
catalog.py — FOSS App Catalog loader and query interface.

Loads `catalog.yaml` from disk and provides fuzzy search so the Provisioner
Agent can map a member's natural-language request to a concrete app entry.

GOVERNANCE CONSTRAINT: This module is read-only at runtime. Adding a new app
to the catalog requires amending `catalog.yaml` via a democratic vote (same
HITL process as AJD approval). The Provisioner Agent MUST NOT deploy any
image not present in this catalog.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Catalog lives next to this file.
_CATALOG_PATH = Path(__file__).parent / "catalog.yaml"


class AppCatalog:
    """
    Loads and queries the vetted FOSS app catalog.

    Usage:
        catalog = AppCatalog()
        entry = catalog.get("nextcloud")
        matches = catalog.search("file sharing collaboration")
    """

    def __init__(self, catalog_path: Path = _CATALOG_PATH) -> None:
        self._path = catalog_path
        self._apps: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Parse catalog.yaml into an in-memory dict keyed by app name."""
        if not self._path.exists():
            logger.error("App catalog not found at %s", self._path)
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        for entry in raw.get("apps", []):
            self._apps[entry["name"].lower()] = entry
        logger.info("AppCatalog loaded: %d apps", len(self._apps))

    # ── Query Interface ───────────────────────────────────────────────────────

    def get(self, name: str) -> dict[str, Any] | None:
        """Exact-match lookup by app name (case-insensitive)."""
        return self._apps.get(name.lower())

    def all(self) -> list[dict[str, Any]]:
        """Return all catalog entries."""
        return list(self._apps.values())

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """
        Keyword search across name, description, and category fields.

        Scores each entry by the number of query tokens that appear in its
        searchable text. Returns up to `top_k` entries sorted by score desc.

        In production, replace with a vector similarity search against
        embedded descriptions (pgvector + nomic-embed-text).
        """
        tokens = set(query.lower().split())
        scored: list[tuple[int, dict[str, Any]]] = []

        for entry in self._apps.values():
            searchable = " ".join([
                entry.get("name", ""),
                entry.get("description", ""),
                entry.get("category", ""),
            ]).lower()
            score = sum(1 for tok in tokens if tok in searchable)
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def is_allowed_image(self, docker_image: str) -> bool:
        """
        Security gate: returns True only if the image is in the catalog.

        The Provisioner Agent calls this before any Docker pull/create call.
        Prevents deployment of arbitrary images not vetted by the cooperative.
        """
        allowed = {e["docker_image"] for e in self._apps.values()}
        # Strip tag for partial match (e.g. "nextcloud:28-apache" → "nextcloud").
        base = docker_image.split(":")[0]
        return docker_image in allowed or any(
            a.startswith(base) for a in allowed
        )

    def categories(self) -> list[str]:
        """Return sorted list of unique categories in the catalog."""
        return sorted({e.get("category", "uncategorized") for e in self._apps.values()})
