/**
 * DisCO Ledger Page — Contributory accounting display.
 *
 * Replaces frontend/pages/ledger.py.
 * Read-only with optional auth for contribution submission.
 */
"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";

export default function LedgerPage() {
  const { user, isAuthenticated } = useAuth();

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-iskander-200">DisCO Ledger</h1>

      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        <h2 className="text-lg font-semibold text-iskander-300 mb-4">
          Contributory Accounting
        </h2>
        <p className="text-iskander-500 text-sm">
          The DisCO ledger tracks all cooperative contributions — productive work,
          care work, and love work. Contributions are validated via the Steward
          Agent (Phase 17: opt-in claim model with peer witness verification).
        </p>

        {/* Placeholder for contribution table */}
        <div className="mt-6 bg-iskander-950 rounded-lg p-4">
          <div className="grid grid-cols-4 gap-2 text-xs text-iskander-500 font-medium border-b border-iskander-800 pb-2 mb-2">
            <span>Member</span>
            <span>Type</span>
            <span>Hours</span>
            <span>Status</span>
          </div>
          <p className="text-iskander-600 text-xs py-4 text-center">
            No contributions recorded yet. Submit via POST /steward/contribute.
          </p>
        </div>
      </div>

      {isAuthenticated && (
        <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
          <h2 className="text-lg font-semibold text-iskander-300 mb-4">
            Submit Contribution
          </h2>
          <p className="text-iskander-500 text-sm">
            Contribution submission via the Steward Agent will be available here.
            Currently accessible via POST /steward/contribute API.
          </p>
        </div>
      )}
    </div>
  );
}
