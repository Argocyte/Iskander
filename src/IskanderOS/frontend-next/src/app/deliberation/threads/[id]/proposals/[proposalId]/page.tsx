"use client";

import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { deliberation } from '@/lib/api';
import { ProposalDetail, StanceResponse } from '@/types';
import { ProcessTypeBadge } from '@/components/deliberation/ProcessTypeBadge';
import { StatusBadge } from '@/components/deliberation/StatusBadge';
import { TallyBar } from '@/components/deliberation/TallyBar';
import { StanceForm } from '@/components/deliberation/StanceForm';
import { StanceList } from '@/components/deliberation/StanceList';
import { OutcomeDisplay } from '@/components/deliberation/OutcomeDisplay';

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function useCountdown(closingAt: string | null, status: string) {
  const [countdown, setCountdown] = useState<string | null>(null);

  useEffect(() => {
    if (!closingAt || status !== 'open') {
      setCountdown(null);
      return;
    }

    function compute() {
      const diffMs = new Date(closingAt!).getTime() - Date.now();
      if (diffMs <= 0) {
        setCountdown('Closing soon');
        return;
      }
      const totalMinutes = Math.floor(diffMs / 60000);
      const hours = Math.floor(totalMinutes / 60);
      const minutes = totalMinutes % 60;
      const days = Math.floor(hours / 24);
      const remHours = hours % 24;

      if (totalMinutes < 60) {
        setCountdown('Closing soon');
      } else if (days > 0) {
        setCountdown(`Closes in ${days}d ${remHours}h`);
      } else {
        setCountdown(`Closes in ${hours}h ${minutes}m`);
      }
    }

    compute();
    const timer = setInterval(compute, 60000);
    return () => clearInterval(timer);
  }, [closingAt, status]);

  return countdown;
}

export default function ProposalDetailPage() {
  const { id, proposalId } = useParams<{ id: string; proposalId: string }>();
  const { user } = useAuth();

  const [proposal, setProposal] = useState<ProposalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const countdown = useCountdown(proposal?.closing_at ?? null, proposal?.status ?? '');

  const fetchProposal = useCallback(() => {
    setLoading(true);
    setError(null);
    deliberation
      .getProposal(id, proposalId)
      .then((data) => setProposal(data))
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : 'Failed to load proposal.';
        setError(message);
      })
      .finally(() => setLoading(false));
  }, [id, proposalId]);

  useEffect(() => {
    fetchProposal();
  }, [fetchProposal]);

  // ── Loading ──────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="max-w-3xl mx-auto space-y-8">
        <p className="text-iskander-500 text-sm">Loading proposal...</p>
      </div>
    );
  }

  // ── Error ────────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="max-w-3xl mx-auto space-y-8">
        <Link href={`/deliberation/threads/${id}`} className="text-iskander-500 hover:text-iskander-300 text-sm">
          ← Back to thread
        </Link>
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  // ── Not found ────────────────────────────────────────────────────────────────
  if (!proposal) {
    return (
      <div className="max-w-3xl mx-auto space-y-8">
        <Link href={`/deliberation/threads/${id}`} className="text-iskander-500 hover:text-iskander-300 text-sm">
          ← Back to thread
        </Link>
        <p className="text-iskander-500 text-sm">Proposal not found.</p>
      </div>
    );
  }

  const myDid = user?.did ?? user?.address ?? null;
  const myStance = myDid
    ? proposal.stances.find((s) => s.member_did === myDid) ?? null
    : null;

  function handleStanceCast(newStance: StanceResponse) {
    // Refetch to get fresh tally + stances from the server
    fetchProposal();
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* 1. Back link */}
      <Link href={`/deliberation/threads/${id}`} className="text-iskander-500 hover:text-iskander-300 text-sm">
        ← Back to thread
      </Link>

      {/* 2. Header card */}
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        {/* Row 1: title + badges */}
        <div className="flex items-start gap-3 flex-wrap">
          <h1 className="text-2xl font-bold text-iskander-200 flex-1">{proposal.title}</h1>
          <ProcessTypeBadge processType={proposal.process_type} />
          <StatusBadge status={proposal.status} />
        </div>

        {/* Row 2: author DID + created date */}
        <div className="flex items-center gap-3 mt-3">
          <span className="text-iskander-500 text-sm font-mono truncate max-w-xs">
            {proposal.author_did}
          </span>
          <span className="text-iskander-600 text-xs shrink-0">
            {formatDate(proposal.created_at)}
          </span>
        </div>

        {/* Row 3: closing countdown */}
        {countdown && (
          <p className="mt-2 text-iskander-400 text-sm">{countdown}</p>
        )}

        {/* Row 4: quorum */}
        {proposal.quorum_pct > 0 && (
          <p className="mt-1 text-iskander-500 text-xs">
            Quorum: {proposal.quorum_pct}%
          </p>
        )}
      </div>

      {/* 3. Body card */}
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        {proposal.ai_draft !== null && (
          <span className="inline-block mb-3 text-xs bg-iskander-800 text-iskander-500 rounded px-2 py-0.5">
            AI-drafted proposal
          </span>
        )}
        <p className="text-iskander-300 text-sm whitespace-pre-wrap">{proposal.body}</p>
      </div>

      {/* 4. Tally bar */}
      <TallyBar tally={proposal.tally} processType={proposal.process_type} />

      {/* 5. Stance form (open proposals only) */}
      {proposal.status === 'open' && (
        <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
          <h2 className="text-lg font-semibold text-iskander-300 mb-4">
            {myStance ? 'Update your vote' : 'Cast your vote'}
          </h2>
          <StanceForm
            threadId={id}
            proposalId={proposalId}
            processType={proposal.process_type}
            options={proposal.options}
            existingStance={myStance}
            onStanceCast={handleStanceCast}
          />
        </div>
      )}

      {/* 6. Stance list */}
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        <h2 className="text-lg font-semibold text-iskander-300 mb-4">
          Votes ({proposal.stance_count})
        </h2>
        <StanceList stances={proposal.stances} processType={proposal.process_type} />
      </div>

      {/* 7. Outcome display */}
      <OutcomeDisplay outcome={proposal.outcome} proposalStatus={proposal.status} />
    </div>
  );
}
