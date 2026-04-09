"""
backend.mesh — Mesh Archive / Sovereign Data Fabric (Phase 25).

Content-addressed, permission-aware distributed storage built on IPFS.
All data is encrypted per-audience before pinning. Access is gated by
gSBT identity tokens — the cooperative controls its own data.

Public API
----------
SovereignStorage   — IPFS pin/cat/ls with audience-scoped encryption.
requires_access    — Decorator enforcing gSBT access checks.
CausalEvent        — Immutable, encrypted event creation and pinning.
DeltaSyncProtocol  — Peer-to-peer CID synchronisation with access filtering.
"""
from __future__ import annotations

from backend.mesh.sovereign_storage import SovereignStorage
from backend.mesh.access_middleware import requires_access
from backend.mesh.causal_event import CausalEvent
from backend.mesh.delta_sync import DeltaSyncProtocol

__all__ = [
    "SovereignStorage",
    "requires_access",
    "CausalEvent",
    "DeltaSyncProtocol",
]
