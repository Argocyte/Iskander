/**
 * Governance Page — Proposal list, submit, vote.
 *
 * Replaces frontend/pages/governance.py.
 * Protected: requires SIWE auth for POST actions.
 */
"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { governance } from "@/lib/api";

export default function GovernancePage() {
  const { user, isAuthenticated } = useAuth();
  const [description, setDescription] = useState("");
  const [toAddress, setToAddress] = useState("");
  const [valueWei, setValueWei] = useState("0");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;

    setLoading(true);
    setError(null);

    try {
      const res = await governance.propose({
        description,
        to: toAddress || undefined,
        value_wei: parseInt(valueWei, 10),
        proposed_by: user.did || user.address,
      });
      setResult(res);
      setDescription("");
      setToAddress("");
      setValueWei("0");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Proposal failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-iskander-200">Governance</h1>

      {/* Submit Proposal */}
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        <h2 className="text-lg font-semibold text-iskander-300 mb-4">
          Submit Proposal
        </h2>

        {!isAuthenticated ? (
          <p className="text-iskander-500 text-sm">
            Sign in with your wallet to submit governance proposals.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-iskander-400 mb-1">
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                required
                rows={3}
                className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-3 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
                placeholder="Describe your governance proposal..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-iskander-400 mb-1">
                  To Address (optional)
                </label>
                <input
                  type="text"
                  value={toAddress}
                  onChange={(e) => setToAddress(e.target.value)}
                  className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm font-mono focus:border-iskander-500 focus:outline-none"
                  placeholder="0x..."
                />
              </div>
              <div>
                <label className="block text-sm text-iskander-400 mb-1">
                  Value (wei)
                </label>
                <input
                  type="number"
                  value={valueWei}
                  onChange={(e) => setValueWei(e.target.value)}
                  className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !description}
              className="px-4 py-2 bg-iskander-600 text-white rounded-lg hover:bg-iskander-500 transition-colors disabled:opacity-50"
            >
              {loading ? "Submitting..." : "Submit Proposal"}
            </button>
          </form>
        )}

        {error && <p className="text-red-400 text-sm mt-3">{error}</p>}

        {result && (
          <div className="mt-4 bg-iskander-950 rounded-lg p-4">
            <p className="text-iskander-300 text-sm font-medium">
              Proposal submitted!
            </p>
            <p className="text-iskander-500 text-xs mt-1 font-mono">
              Thread ID: {String(result.thread_id)}
            </p>
            <p className="text-iskander-500 text-xs">
              Status: {String(result.status)}
            </p>
          </div>
        )}
      </div>

      {/* ICA Principle 2: Democratic Member Control */}
      <div className="bg-iskander-950 rounded-xl p-4 border border-iskander-800">
        <p className="text-xs text-iskander-600">
          ICA Principle 2: Democratic Member Control. All proposals require HITL
          approval by stewards via the Safe multi-sig. One member, one vote.
          MACI provides ZK-SNARK vote privacy.
        </p>
      </div>
    </div>
  );
}
