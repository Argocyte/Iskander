'use client'

import { useState } from 'react'
import { StanceResponse } from '@/types'

interface StanceListProps {
  stances: StanceResponse[]
  processType: string
}

const stancePillColors: Record<string, string> = {
  agree:    'bg-green-900/50 text-green-300',
  abstain:  'bg-gray-800 text-gray-300',
  disagree: 'bg-orange-900/50 text-orange-300',
  block:    'bg-red-900/50 text-red-300',
}

function truncateDid(did: string, maxLen = 20): string {
  return did.length > maxLen ? did.slice(0, maxLen) + '\u2026' : did
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

export function StanceList({ stances, processType }: StanceListProps) {
  const [expanded, setExpanded] = useState(false)

  if (stances.length === 0) {
    return <p className="text-iskander-500 text-sm">No stances cast yet.</p>
  }

  const visible = expanded ? stances : stances.slice(0, 5)
  const hasMore = stances.length > 5

  return (
    <div className="space-y-2">
      {visible.map((stance) => (
        <div key={stance.id} className="bg-iskander-950 rounded-lg p-3 space-y-1">
          {/* Row 1: member + pill + timestamp */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-iskander-400 text-xs font-mono">
              {truncateDid(stance.member_did)}
            </span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
                stancePillColors[stance.stance] ?? 'bg-iskander-800 text-iskander-400'
              }`}
            >
              {stance.stance}
            </span>
            <span className="text-iskander-600 text-xs ml-auto">
              {formatTimestamp(stance.created_at)}
            </span>
          </div>

          {/* Row 2: reason */}
          {stance.reason && (
            <p className="text-iskander-300 text-sm italic">{stance.reason}</p>
          )}

          {/* Score badge for score process */}
          {processType === 'score' && stance.score !== null && (
            <span className="inline-block bg-iskander-800 text-iskander-300 text-xs rounded px-2 py-0.5">
              Score: {stance.score}
            </span>
          )}

          {/* Rank order for rank process */}
          {processType === 'rank' && stance.rank_order && stance.rank_order.length > 0 && (
            <ol className="list-decimal list-inside text-iskander-300 text-xs space-y-0.5 mt-1">
              {stance.rank_order.map((item, idx) => (
                <li key={idx}>{JSON.stringify(item)}</li>
              ))}
            </ol>
          )}
        </div>
      ))}

      {hasMore && !expanded && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="text-iskander-500 hover:text-iskander-300 text-xs"
        >
          Show all {stances.length} stances
        </button>
      )}

      {hasMore && expanded && (
        <button
          type="button"
          onClick={() => setExpanded(false)}
          className="text-iskander-500 hover:text-iskander-300 text-xs"
        >
          Show fewer
        </button>
      )}
    </div>
  )
}
