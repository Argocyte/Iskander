"""
websocket_notifier.py — Phase 16: Asynchronous WebSocket Status Bus.

Provides a single broadcast channel that:
  1. Pushes JSON events to all connected WebSocket clients
     (Streamlit dashboard, external tooling).
  2. Exposes an internal asyncio pub/sub queue so that LangGraph nodes
     and the Matrix bridge can subscribe without opening a real WebSocket.

Endpoint: GET /ws/events  (WebSocket upgrade)

Event schema:
  {
    "task_id":   "<uuid | null>",
    "agent_id":  "<agent identifier>",
    "event":     "queued | running | node_entered | node_exited |
                  hitl_required | task_complete | error | queue_rejected",
    "node":      "<LangGraph node name | null>",
    "timestamp": "<ISO-8601>",
    "payload":   {}
  }

Security:
  Dev mode: unauthenticated (acceptable on LAN-only deployment).
  Production: add Bearer token middleware before mounting this route.
  Pattern matches `backend/matrix/appservice.py` HS token verification.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])

# Maximum number of events retained in the internal replay buffer.
# New connections receive the last N events so they catch up.
_REPLAY_BUFFER_SIZE = 100


class WebSocketNotifier:
    """
    Singleton broadcast bus.

    External callers (LangGraph nodes, AsyncAgentQueue, Matrix bridge):
        notifier = WebSocketNotifier.get_instance()
        await notifier.broadcast({"event": "hitl_required", "task_id": "..."})

    Internal subscriber (Matrix bridge, unit tests):
        async for event in notifier.subscribe():
            handle(event)
    """

    _instance: WebSocketNotifier | None = None

    def __init__(self) -> None:
        # Active WebSocket connections.
        self._connections: list[WebSocket] = []
        # Internal subscribers (asyncio.Queue per subscriber).
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        # Replay buffer for late joiners.
        self._buffer: list[dict[str, Any]] = []

    @classmethod
    def get_instance(cls) -> WebSocketNotifier:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Broadcast ─────────────────────────────────────────────────────────────

    async def broadcast(self, event: dict[str, Any]) -> None:
        """
        Send an event to all connected WebSocket clients and internal subscribers.
        Silently drops to dead connections.
        """
        # Stamp the event.
        event.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        event.setdefault("task_id",   None)
        event.setdefault("agent_id",  None)
        event.setdefault("node",      None)
        event.setdefault("payload",   {})

        # Append to replay buffer (rolling window).
        self._buffer.append(event)
        if len(self._buffer) > _REPLAY_BUFFER_SIZE:
            self._buffer.pop(0)

        # Push to WebSocket clients.
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)

        # Push to internal subscribers.
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Slow subscriber — drop event rather than block.

    # ── Internal pub/sub ──────────────────────────────────────────────────────

    def subscribe(self) -> _InternalSubscription:
        """
        Return an async context manager that yields events from the bus.

        Usage:
            async with notifier.subscribe() as events:
                async for event in events:
                    ...
        """
        return _InternalSubscription(self)

    def _attach_queue(self, q: asyncio.Queue) -> None:
        self._subscribers.append(q)

    def _detach_queue(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    # ── Connection management ─────────────────────────────────────────────────

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        # Replay recent events to the new client.
        for event in self._buffer[-_REPLAY_BUFFER_SIZE:]:
            try:
                await ws.send_json(event)
            except Exception:
                break
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        try:
            self._connections.remove(ws)
        except ValueError:
            pass
        logger.info("WebSocket client disconnected (%d remaining)", len(self._connections))

    def active_connections(self) -> int:
        return len(self._connections)


class _InternalSubscription:
    """Async context manager for internal event subscriptions."""

    def __init__(self, notifier: WebSocketNotifier) -> None:
        self._notifier = notifier
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)

    async def __aenter__(self) -> asyncio.Queue:
        self._notifier._attach_queue(self._queue)
        return self._queue

    async def __aexit__(self, *_) -> None:
        self._notifier._detach_queue(self._queue)


# ── FastAPI WebSocket endpoint ────────────────────────────────────────────────

@router.websocket("/ws/events")
async def websocket_events(
    ws: WebSocket,
    token: str | None = None,
) -> None:
    """
    WebSocket endpoint. Clients connect and receive a JSON stream of
    agent status events for the lifetime of their connection.

    Phase 19: Optional JWT authentication via query parameter:
        ws://host:8000/ws/events?token=<jwt>
    Falls back to unauthenticated in dev mode (chain_id == 31337).
    """
    # Phase 19: Optional token-based auth for WebSocket connections.
    if token:
        try:
            from backend.auth.jwt_manager import verify_token
            verify_token(token, expected_type="access")
            logger.info("WebSocket client authenticated via token")
        except (ValueError, Exception) as exc:
            from backend.config import settings as _ws_settings
            if _ws_settings.evm_chain_id != 31337:
                await ws.close(code=4001, reason="Invalid token")
                return
            logger.warning("WebSocket token invalid (%s) — allowed in dev mode", exc)

    notifier = WebSocketNotifier.get_instance()
    await notifier.connect(ws)
    try:
        while True:
            # Keep the connection alive by reading (and discarding) any pings
            # sent by the client. Actual events are pushed via broadcast().
            await ws.receive_text()
    except WebSocketDisconnect:
        notifier.disconnect(ws)
    except Exception:
        notifier.disconnect(ws)
