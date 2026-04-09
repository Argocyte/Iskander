"""
backend.matrix
~~~~~~~~~~~~~~
Phase 14A: Embedded Dendrite Matrix homeserver integration.

Provides:
  MatrixClient    — async wrapper around matrix-nio for sending/receiving messages.
  AppServiceHandler — routes incoming Matrix events to Iskander agent graphs.
  AgentBridge     — maps agent IDs to dedicated bot users and rooms.
"""
from backend.matrix.client import MatrixClient
from backend.matrix.bridge import AgentBridge

__all__ = ["MatrixClient", "AgentBridge"]
