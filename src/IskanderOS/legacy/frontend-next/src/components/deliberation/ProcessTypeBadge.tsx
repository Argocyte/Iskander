interface ProcessTypeBadgeProps {
  processType: string
  showLabel?: boolean
}

const colorMap: Record<string, string> = {
  sense_check: 'bg-blue-900/50 text-blue-300',
  advice:      'bg-teal-900/50 text-teal-300',
  consent:     'bg-green-900/50 text-green-300',
  consensus:   'bg-emerald-900/50 text-emerald-300',
  choose:      'bg-purple-900/50 text-purple-300',
  score:       'bg-orange-900/50 text-orange-300',
  allocate:    'bg-amber-900/50 text-amber-300',
  rank:        'bg-pink-900/50 text-pink-300',
  time_poll:   'bg-cyan-900/50 text-cyan-300',
}

function formatLabel(processType: string): string {
  return processType
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function ProcessTypeBadge({ processType, showLabel = true }: ProcessTypeBadgeProps) {
  const colorClass = colorMap[processType] ?? 'bg-iskander-800 text-iskander-400'
  const label      = formatLabel(processType)

  // When showLabel=false, renders a color-only dot (intentional for compact layouts)
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${colorClass}`}
      {...(!showLabel && { 'aria-label': label })}
    >
      {showLabel ? label : null}
    </span>
  )
}
