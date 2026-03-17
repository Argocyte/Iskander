/**
 * useWebSocket.ts — Phase 19: WebSocket Hook for Real-Time Events.
 *
 * Connects to /ws/events with optional JWT authentication.
 * Auto-reconnects with exponential backoff.
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getAccessToken } from "@/lib/api";

interface WebSocketEvent {
  task_id: string | null;
  agent_id: string | null;
  event: string;
  node: string | null;
  timestamp: string;
  payload: Record<string, unknown>;
}

interface UseWebSocketOptions {
  maxRetries?: number;
  maxBackoff?: number;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { maxRetries = 10, maxBackoff = 30000 } = options;

  const [events, setEvents] = useState<WebSocketEvent[]>([]);
  const [lastEvent, setLastEvent] = useState<WebSocketEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = process.env.NEXT_PUBLIC_API_URL?.replace(/^https?:\/\//, "") || "localhost:8000";
    const token = getAccessToken();
    const tokenParam = token ? `?token=${token}` : "";
    const url = `${wsProtocol}//${host}/ws/events${tokenParam}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setIsConnected(true);
      retriesRef.current = 0;
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const data: WebSocketEvent = JSON.parse(event.data);
        setLastEvent(data);
        setEvents((prev) => [...prev.slice(-99), data]);
      } catch {
        // Ignore malformed messages.
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setIsConnected(false);

      // Exponential backoff reconnect.
      if (retriesRef.current < maxRetries) {
        const delay = Math.min(1000 * 2 ** retriesRef.current, maxBackoff);
        retriesRef.current += 1;
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [maxRetries, maxBackoff]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, [connect]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, lastEvent, isConnected, clearEvents };
}
