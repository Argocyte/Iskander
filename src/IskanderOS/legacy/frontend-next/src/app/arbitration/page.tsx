/**
 * Arbitration Page — File disputes, view cases, jury info, verdicts.
 *
 * NEW page (backend API existed, no previous Streamlit UI).
 */
"use client";

export default function ArbitrationPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-iskander-200">Solidarity Court</h1>

      <div className="bg-iskander-950 rounded-xl p-8 border border-iskander-800 text-center">
        <p className="text-iskander-400 text-lg">Coming Soon</p>
        <p className="text-iskander-600 text-sm mt-2">
          This module is under active development.
        </p>
      </div>

      <div className="bg-iskander-950 rounded-xl p-4 border border-iskander-800">
        <p className="text-xs text-iskander-600">
          Arbitration follows ICA Principle 6: Cooperation Among Cooperatives.
          Federated juries prevent capture by any single cooperative. The NY Convention
          arbitration clause in the Ricardian contract ensures meatspace enforceability.
        </p>
      </div>
    </div>
  );
}
