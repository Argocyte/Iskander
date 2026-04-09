/**
 * Agent Chat Page — Agentic chat interface via WebSocket.
 *
 * Replaces frontend/pages/chat.py.
 * Auth required to submit prompts.
 */
"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useWebSocket } from "@/hooks/useWebSocket";

export default function ChatPage() {
  const { isAuthenticated } = useAuth();
  const { events, isConnected } = useWebSocket();
  const [input, setInput] = useState("");

  return (
    <div className="max-w-3xl mx-auto space-y-8 h-full flex flex-col">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-iskander-200">Agent Chat</h1>
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              isConnected ? "bg-green-400" : "bg-red-400"
            }`}
          />
          <span className="text-xs text-iskander-500">
            {isConnected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </div>

      {/* Event Stream */}
      <div className="flex-1 bg-iskander-900 rounded-xl border border-iskander-800 overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto p-4 space-y-2 max-h-96">
          {events.length === 0 ? (
            <p className="text-iskander-600 text-sm text-center py-8">
              Waiting for agent events...
            </p>
          ) : (
            events.map((event, i) => (
              <div
                key={i}
                className="bg-iskander-950 rounded-lg p-3 text-xs space-y-1"
              >
                <div className="flex items-center gap-2">
                  <span className="text-iskander-400 font-medium">
                    {event.event}
                  </span>
                  {event.agent_id && (
                    <span className="text-iskander-600">{event.agent_id}</span>
                  )}
                  {event.node && (
                    <span className="text-iskander-500 font-mono">
                      [{event.node}]
                    </span>
                  )}
                </div>
                <p className="text-iskander-600">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </p>
              </div>
            ))
          )}
        </div>

        {/* Input */}
        <div className="border-t border-iskander-800 p-4">
          {!isAuthenticated ? (
            <p className="text-iskander-500 text-sm text-center">
              Sign in to interact with agents.
            </p>
          ) : (
            <div className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Send a message to the agent..."
                className="flex-1 bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
              />
              <button className="px-4 py-2 bg-iskander-600 text-white rounded-lg hover:bg-iskander-500 transition-colors text-sm">
                Send
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
