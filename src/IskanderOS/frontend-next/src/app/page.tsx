/**
 * Home Page — Node health, system status, quick links.
 */
"use client";

import { useEffect, useState } from "react";
import { system } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";

interface HealthData {
  status: string;
  node: string;
  evm_chain_id: number;
  llm_model: string;
  queue_depth: number;
  ws_connections: number;
}

export default function HomePage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { lastEvent, isConnected } = useWebSocket();

  useEffect(() => {
    system
      .health()
      .then(setHealth)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-iskander-200">Iskander Node</h1>
        <p className="text-iskander-500 mt-2">
          Sovereign cooperative operating system — Phase 19: Web3 Integration
        </p>
      </div>

      {/* Health Status */}
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        <h2 className="text-lg font-semibold text-iskander-300 mb-4">Node Status</h2>
        {error ? (
          <p className="text-red-400">{error}</p>
        ) : health ? (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <StatusCard label="Status" value={health.status} />
            <StatusCard label="Domain" value={health.node} />
            <StatusCard label="Chain ID" value={String(health.evm_chain_id)} />
            <StatusCard label="LLM Model" value={health.llm_model} />
            <StatusCard label="Queue Depth" value={String(health.queue_depth)} />
            <StatusCard label="WS Clients" value={String(health.ws_connections)} />
          </div>
        ) : (
          <p className="text-iskander-500 animate-pulse">Loading...</p>
        )}
      </div>

      {/* WebSocket Status */}
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        <div className="flex items-center gap-2 mb-4">
          <div
            className={`w-2 h-2 rounded-full ${
              isConnected ? "bg-green-400" : "bg-red-400"
            }`}
          />
          <h2 className="text-lg font-semibold text-iskander-300">
            Real-Time Events
          </h2>
        </div>
        {lastEvent ? (
          <pre className="text-xs text-iskander-400 bg-iskander-950 p-3 rounded overflow-x-auto">
            {JSON.stringify(lastEvent, null, 2)}
          </pre>
        ) : (
          <p className="text-iskander-600 text-sm">Waiting for events...</p>
        )}
      </div>
    </div>
  );
}

function StatusCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-iskander-950 rounded-lg p-3">
      <p className="text-xs text-iskander-500">{label}</p>
      <p className="text-sm font-medium text-iskander-200 mt-1">{value}</p>
    </div>
  );
}
