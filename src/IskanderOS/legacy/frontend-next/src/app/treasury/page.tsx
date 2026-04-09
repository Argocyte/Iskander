/**
 * Treasury Page — Payment submission, Mondragon ratio, HITL approval.
 *
 * NEW page (backend API existed, no previous Streamlit UI).
 * Protected: requires steward role for all mutations.
 */
"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { treasury } from "@/lib/api";

export default function TreasuryPage() {
  const { user, isAuthenticated } = useAuth();
  const isSteward = user?.role === "steward";
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [paymentType, setPaymentType] = useState("internal_payroll");
  const [toAddress, setToAddress] = useState("");
  const [amount, setAmount] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await treasury.submitPayment({
        type: paymentType,
        to: toAddress,
        amount: parseFloat(amount),
        lowest_member_pay: 1.0,
        ratio_cap: 6.0,
      });
      setResult(res as Record<string, unknown>);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Payment failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-iskander-200">Treasury</h1>

      {/* Mondragon Ratio Gauge */}
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        <h2 className="text-lg font-semibold text-iskander-300 mb-4">
          Mondragon Pay Ratio
        </h2>
        <div className="flex items-center gap-4">
          <div className="flex-1 bg-iskander-950 rounded-full h-4 overflow-hidden">
            <div
              className="bg-solidarity h-full rounded-full transition-all"
              style={{ width: "50%" }}
            />
          </div>
          <span className="text-iskander-300 text-sm font-mono">3:1 / 6:1</span>
        </div>
        <p className="text-xs text-iskander-600 mt-2">
          ICA Principle 3: Members contribute equitably to capital. The Mondragon
          model caps the highest:lowest pay ratio at 6:1.
        </p>
      </div>

      {/* Payment Form */}
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        <h2 className="text-lg font-semibold text-iskander-300 mb-4">
          Submit Payment
        </h2>

        {!isAuthenticated || !isSteward ? (
          <p className="text-iskander-500 text-sm">
            {!isAuthenticated
              ? "Sign in to access treasury functions."
              : "Treasury payments require steward role."}
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-iskander-400 mb-1">Type</label>
              <select
                value={paymentType}
                onChange={(e) => setPaymentType(e.target.value)}
                className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm"
              >
                <option value="internal_payroll">Internal Payroll</option>
                <option value="internal_reimbursement">Reimbursement</option>
                <option value="external_vendor">External Vendor</option>
                <option value="treasury_transfer">Treasury Transfer</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-iskander-400 mb-1">
                  Recipient
                </label>
                <input
                  type="text"
                  value={toAddress}
                  onChange={(e) => setToAddress(e.target.value)}
                  required
                  className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm font-mono"
                  placeholder="0x..."
                />
              </div>
              <div>
                <label className="block text-sm text-iskander-400 mb-1">
                  Amount
                </label>
                <input
                  type="number"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  required
                  step="0.01"
                  className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-solidarity text-white rounded-lg hover:bg-solidarity-dark transition-colors disabled:opacity-50"
            >
              {loading ? "Submitting..." : "Submit Payment"}
            </button>
          </form>
        )}

        {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
        {result && (
          <div className="mt-4 bg-iskander-950 rounded-lg p-4">
            <p className="text-iskander-300 text-sm">
              Status: {String(result.status)}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
