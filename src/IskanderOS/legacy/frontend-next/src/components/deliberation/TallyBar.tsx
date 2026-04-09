import { ProposalTally } from '@/types'

interface TallyBarProps {
  tally: ProposalTally | null
  processType: string
}

const STANCE_PROCESSES = ['sense_check', 'advice', 'consent', 'consensus']

const stanceColors: Record<string, { bar: string; dot: string }> = {
  agree:    { bar: 'bg-green-500',  dot: 'bg-green-500' },
  abstain:  { bar: 'bg-gray-500',   dot: 'bg-gray-500' },
  disagree: { bar: 'bg-orange-500', dot: 'bg-orange-500' },
  block:    { bar: 'bg-red-500',    dot: 'bg-red-500' },
}

const stanceOrder = ['agree', 'abstain', 'disagree', 'block'] as const

export function TallyBar({ tally, processType }: TallyBarProps) {
  if (!tally || tally.total === 0) {
    return <p className="text-iskander-500 text-sm">No stances yet</p>
  }

  if (STANCE_PROCESSES.includes(processType)) {
    return <StanceTally tally={tally} />
  }

  return <OptionTally options={tally.options} />
}

/* ── Stance-based horizontal stacked bar ─────────────────────────────────── */

function StanceTally({ tally }: { tally: ProposalTally }) {
  const segments = stanceOrder
    .map((key) => ({
      key,
      count: tally[key],
      pct: (tally[key] / tally.total) * 100,
      color: stanceColors[key].bar,
    }))
    .filter((s) => s.count > 0)

  return (
    <div className="space-y-2">
      {/* Stacked bar */}
      <div className="h-4 rounded-full overflow-hidden flex w-full bg-iskander-800">
        {segments.map((seg) => (
          <div
            key={seg.key}
            className={`${seg.color} h-full`}
            style={{ width: `${seg.pct}%` }}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3">
        {stanceOrder.map((key) => {
          const count = tally[key]
          if (count === 0) return null
          return (
            <span key={key} className="flex items-center gap-1 text-iskander-400 text-xs">
              <span className={`w-3 h-3 rounded-full ${stanceColors[key].dot}`} />
              <span className="capitalize">{key}</span>
              <span>{count}</span>
            </span>
          )
        })}
      </div>
    </div>
  )
}

/* ── Option-based individual bars ────────────────────────────────────────── */

function OptionTally({ options }: { options: Record<string, number> }) {
  const entries = Object.entries(options).sort(([, a], [, b]) => b - a)
  const maxValue = entries.length > 0 ? entries[0][1] : 1

  return (
    <div className="space-y-2">
      {entries.map(([label, value]) => {
        const pct = maxValue > 0 ? (value / maxValue) * 100 : 0
        return (
          <div key={label} className="space-y-1">
            <div className="flex justify-between text-iskander-300 text-sm">
              <span>{label}</span>
              <span>{value}</span>
            </div>
            <div className="h-3 rounded-full bg-iskander-800 overflow-hidden">
              <div
                className="h-full rounded-full bg-iskander-500"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
