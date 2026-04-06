"use client";

import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { deliberation } from '@/lib/api';
import { ProcessTypeBadge } from '@/components/deliberation/ProcessTypeBadge';
import type { ProcessType, ProposalDetail } from '@/types';

interface CreateProposalFormProps {
  threadId: string;
  onProposalCreated: (proposal: ProposalDetail) => void;
  onClose: () => void;
}

const PROCESS_TYPES: { value: ProcessType; desc: string }[] = [
  { value: 'sense_check', desc: 'Temperature check' },
  { value: 'advice',      desc: 'Seek input' },
  { value: 'consent',     desc: 'Proceed unless objection' },
  { value: 'consensus',   desc: 'Everyone must agree' },
  { value: 'choose',      desc: 'Pick one option' },
  { value: 'score',       desc: 'Rate options' },
  { value: 'allocate',    desc: 'Distribute points' },
  { value: 'rank',        desc: 'Order preference' },
  { value: 'time_poll',   desc: 'Find a time' },
];

const OPTION_TYPES: ProcessType[] = ['choose', 'score', 'allocate', 'rank', 'time_poll'];

export function CreateProposalForm({
  threadId,
  onProposalCreated,
  onClose,
}: CreateProposalFormProps) {
  const { user } = useAuth();
  const [processType, setProcessType] = useState<ProcessType>('sense_check');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [options, setOptions] = useState<string[]>([]);
  const [optionInput, setOptionInput] = useState('');
  const [quorumPct, setQuorumPct] = useState(0);
  const [closingAt, setClosingAt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const needsOptions = OPTION_TYPES.includes(processType);
  const canSubmit =
    title.trim() &&
    !submitting &&
    (!needsOptions || options.length >= 2);

  function addOption() {
    const val = optionInput.trim();
    if (val && !options.includes(val)) {
      setOptions((prev) => [...prev, val]);
      setOptionInput('');
    }
  }

  function removeOption(idx: number) {
    setOptions((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || !user) return;

    setSubmitting(true);
    setError(null);

    try {
      const proposal = await deliberation.createProposal(threadId, {
        thread_id: threadId,
        title: title.trim(),
        body: body.trim(),
        process_type: processType,
        author_did: user.did || user.address,
        options: options.length > 0 ? options : undefined,
        quorum_pct: quorumPct || undefined,
        closing_at: closingAt || undefined,
      });
      onProposalCreated(proposal);
      onClose();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create proposal.';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800 w-full max-w-lg max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-iskander-200">New Proposal</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-iskander-500 hover:text-iskander-300 text-lg"
          >
            &#x2715;
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Process Type Selector */}
          <div>
            <label className="block text-iskander-400 text-sm mb-2">Process Type</label>
            <div className="grid grid-cols-3 gap-2">
              {PROCESS_TYPES.map((pt) => (
                <button
                  key={pt.value}
                  type="button"
                  onClick={() => setProcessType(pt.value)}
                  className={`rounded-lg p-2 border text-left transition-colors ${
                    processType === pt.value
                      ? 'bg-iskander-700 border-iskander-500'
                      : 'bg-iskander-950 border-iskander-800 hover:border-iskander-700'
                  }`}
                >
                  <ProcessTypeBadge processType={pt.value} />
                  <p className="text-iskander-500 text-xs mt-1">{pt.desc}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Conditional Options */}
          {needsOptions && (
            <div>
              <label className="block text-iskander-400 text-sm mb-1">
                Options (at least 2 required)
              </label>
              {options.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-2">
                  {options.map((opt, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1 bg-iskander-800 text-iskander-300 rounded-full px-2 py-0.5 text-xs"
                    >
                      {opt}
                      <button
                        type="button"
                        onClick={() => removeOption(idx)}
                        className="text-iskander-500 hover:text-iskander-300"
                      >
                        &#x2715;
                      </button>
                    </span>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <input
                  type="text"
                  className="flex-1 bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
                  placeholder="Add an option"
                  value={optionInput}
                  onChange={(e) => setOptionInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addOption();
                    }
                  }}
                />
                <button
                  type="button"
                  onClick={addOption}
                  className="px-3 py-2 bg-iskander-700 text-iskander-200 rounded-lg hover:bg-iskander-600 transition-colors text-sm"
                >
                  Add
                </button>
              </div>
            </div>
          )}

          {/* Title */}
          <div>
            <label className="block text-iskander-400 text-sm mb-1">Title *</label>
            <input
              type="text"
              required
              className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          {/* Body */}
          <div>
            <label className="block text-iskander-400 text-sm mb-1">Body</label>
            <textarea
              className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
              rows={4}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>

          {/* Quorum % */}
          <div>
            <label className="block text-iskander-400 text-sm mb-1">Quorum %</label>
            <input
              type="number"
              min={0}
              max={100}
              className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
              value={quorumPct}
              onChange={(e) => setQuorumPct(Number(e.target.value))}
            />
          </div>

          {/* Closing date */}
          <div>
            <label className="block text-iskander-400 text-sm mb-1">Closing Date</label>
            <input
              type="datetime-local"
              className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
              value={closingAt}
              onChange={(e) => setClosingAt(e.target.value)}
            />
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}

          {/* Footer */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-iskander-700 text-iskander-200 rounded-lg hover:bg-iskander-600 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!canSubmit}
              className="px-4 py-2 bg-iskander-600 text-white rounded-lg hover:bg-iskander-500 disabled:opacity-50 transition-colors"
            >
              {submitting ? 'Creating...' : 'Create Proposal'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
