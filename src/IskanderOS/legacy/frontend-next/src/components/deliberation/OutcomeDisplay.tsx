import { OutcomeResponse } from '@/types'

interface OutcomeDisplayProps {
  outcome: OutcomeResponse | null
  proposalStatus: string
}

const decisionBadge: Record<string, string> = {
  passed:    'bg-green-900/50 text-green-300',
  rejected:  'bg-red-900/50 text-red-300',
  withdrawn: 'bg-iskander-800 text-iskander-400',
  no_quorum: 'bg-amber-900/50 text-amber-300',
}

function formatLabel(decision: string): string {
  return decision
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function truncateDid(did: string, maxLen = 20): string {
  return did.length > maxLen ? did.slice(0, maxLen) + '\u2026' : did
}

export function OutcomeDisplay({ outcome, proposalStatus }: OutcomeDisplayProps) {
  // No outcome + still open → render nothing
  if (!outcome && proposalStatus === 'open') {
    return null
  }

  // No outcome + closed → awaiting
  if (!outcome && proposalStatus === 'closed') {
    return (
      <p className="text-iskander-500 text-sm italic">Awaiting outcome statement</p>
    )
  }

  if (!outcome) return null

  const badgeClass = decisionBadge[outcome.decision_type] ?? 'bg-iskander-800 text-iskander-400'

  return (
    <div className="space-y-3">
      {/* Decision badge + AI indicator */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${badgeClass}`}>
          {formatLabel(outcome.decision_type)}
        </span>
        {outcome.ai_draft && (
          <span className="text-xs bg-iskander-800 text-iskander-500 rounded px-2 py-0.5">
            AI-drafted
          </span>
        )}
      </div>

      {/* Statement */}
      <div className="border-l-4 border-iskander-600 pl-4 py-2">
        <p className="text-iskander-200 text-sm">{outcome.statement}</p>
      </div>

      {/* Stated by + timestamp */}
      <div className="flex items-center gap-2 text-iskander-500 text-xs">
        <span>Stated by {truncateDid(outcome.stated_by)}</span>
        <span>&middot;</span>
        <span>{formatTimestamp(outcome.created_at)}</span>
      </div>
    </div>
  )
}
