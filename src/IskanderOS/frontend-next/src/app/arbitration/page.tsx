/**
 * Arbitration Page — File disputes, view cases, jury info, verdicts.
 *
 * NEW page (backend API existed, no previous Streamlit UI).
 */
"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";

export default function ArbitrationPage() {
  const { user, isAuthenticated } = useAuth();

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-iskander-200">Solidarity Court</h1>

      {/* Active Cases */}
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        <h2 className="text-lg font-semibold text-iskander-300 mb-4">
          Active Cases
        </h2>
        <p className="text-iskander-600 text-sm text-center py-4">
          No active arbitration cases. Disputes are filed via POST /arbitration/disputes.
        </p>
      </div>

      {/* File Dispute */}
      {isAuthenticated && (
        <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
          <h2 className="text-lg font-semibold text-iskander-300 mb-4">
            File a Dispute
          </h2>
          <p className="text-iskander-500 text-sm mb-4">
            Disputes trigger the Arbitrator Agent which selects a federated jury
            of 5 members from across the cooperative network. Deliberation happens
            via Matrix rooms.
          </p>
          <p className="text-iskander-600 text-xs">
            Dispute filing form coming soon. Currently available via API.
          </p>
        </div>
      )}

      {/* Verdict Recording (Steward Only) */}
      {user?.role === "steward" && (
        <div className="bg-iskander-900 rounded-xl p-6 border border-solidarity/20">
          <h2 className="text-lg font-semibold text-solidarity mb-4">
            Record Verdict (Steward)
          </h2>
          <p className="text-iskander-500 text-sm">
            As a steward, you can record jury verdicts to resolve disputes.
            Verdicts may trigger trust score adjustments via ArbitrationRegistry.sol.
          </p>
        </div>
      )}

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
