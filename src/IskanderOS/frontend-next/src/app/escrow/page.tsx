/**
 * Escrow Page — Create, view, release, dispute inter-coop escrows.
 *
 * NEW page (backend API existed, no previous Streamlit UI).
 */
"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { escrow } from "@/lib/api";

export default function EscrowPage() {
  const { user, isAuthenticated } = useAuth();
  const [activeTab, setActiveTab] = useState<"create" | "lookup">("create");

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-iskander-200">Inter-Coop Escrow</h1>

      {/* Tabs */}
      <div className="flex gap-2">
        {(["create", "lookup"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              activeTab === tab
                ? "bg-iskander-700 text-iskander-100"
                : "bg-iskander-900 text-iskander-400 hover:bg-iskander-800"
            }`}
          >
            {tab === "create" ? "Create Escrow" : "Lookup Escrow"}
          </button>
        ))}
      </div>

      {activeTab === "create" && <CreateEscrowForm isAuthenticated={isAuthenticated} />}
      {activeTab === "lookup" && <LookupEscrow />}

      <div className="bg-iskander-950 rounded-xl p-4 border border-iskander-800">
        <p className="text-xs text-iskander-600">
          Escrows use IskanderEscrow.sol on-chain. Upon release, the Phase 18 IPD
          audit system automatically records the outcome in the reputation graph.
          Disputes trigger the Solidarity Court (ArbitrationRegistry).
        </p>
      </div>
    </div>
  );
}

function CreateEscrowForm({ isAuthenticated }: { isAuthenticated: boolean }) {
  const [sellerAddress, setSellerAddress] = useState("");
  const [amount, setAmount] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await escrow.create({
        seller_coop_address: sellerAddress,
        token_address: "0x0000000000000000000000000000000000000000",
        amount_wei: parseInt(amount, 10),
        terms_ipfs_cid: "",
        expires_at: "",
      });
      setResult(res as Record<string, unknown>);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create escrow");
    } finally {
      setLoading(false);
    }
  }

  if (!isAuthenticated) {
    return (
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        <p className="text-iskander-500 text-sm">
          Sign in with your wallet to create escrows.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
      <form onSubmit={handleCreate} className="space-y-4">
        <div>
          <label className="block text-sm text-iskander-400 mb-1">
            Seller Cooperative Address
          </label>
          <input
            type="text"
            value={sellerAddress}
            onChange={(e) => setSellerAddress(e.target.value)}
            required
            className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm font-mono"
            placeholder="0x..."
          />
        </div>
        <div>
          <label className="block text-sm text-iskander-400 mb-1">
            Amount (wei)
          </label>
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
            className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-iskander-600 text-white rounded-lg hover:bg-iskander-500 transition-colors disabled:opacity-50"
        >
          {loading ? "Creating..." : "Create Escrow"}
        </button>
      </form>
      {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
      {result && (
        <div className="mt-4 bg-iskander-950 rounded-lg p-4">
          <p className="text-iskander-300 text-sm">
            Escrow ID: {String(result.escrow_id)}
          </p>
        </div>
      )}
    </div>
  );
}

function LookupEscrow() {
  const [escrowId, setEscrowId] = useState("");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleLookup(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await escrow.get(escrowId);
      setData(res as Record<string, unknown>);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Not found");
    }
  }

  return (
    <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
      <form onSubmit={handleLookup} className="flex gap-3">
        <input
          type="text"
          value={escrowId}
          onChange={(e) => setEscrowId(e.target.value)}
          placeholder="Escrow ID"
          className="flex-1 bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm"
        />
        <button
          type="submit"
          className="px-4 py-2 bg-iskander-700 text-iskander-200 rounded-lg hover:bg-iskander-600 transition-colors"
        >
          Lookup
        </button>
      </form>
      {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
      {data && (
        <pre className="mt-4 text-xs text-iskander-400 bg-iskander-950 p-3 rounded overflow-x-auto">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}
