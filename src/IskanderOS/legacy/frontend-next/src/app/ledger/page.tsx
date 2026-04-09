/**
 * DisCO Ledger Page — Contributory accounting display.
 *
 * Replaces frontend/pages/ledger.py.
 * Read-only with optional auth for contribution submission.
 */
"use client";

export default function LedgerPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-iskander-200">DisCO Ledger</h1>

      <div className="bg-iskander-950 rounded-xl p-8 border border-iskander-800 text-center">
        <p className="text-iskander-400 text-lg">Coming Soon</p>
        <p className="text-iskander-600 text-sm mt-2">
          This module is under active development.
        </p>
      </div>
    </div>
  );
}
