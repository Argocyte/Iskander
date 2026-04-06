interface StatusBadgeProps {
  status: string
  size?: 'sm' | 'md'
}

const colorMap: Record<string, string> = {
  open:      'bg-green-900/50 text-green-300',
  closed:    'bg-iskander-800 text-iskander-400',
  pinned:    'bg-yellow-900/50 text-yellow-300',
  withdrawn: 'bg-red-900/50 text-red-300',
}

const sizeMap = {
  sm: 'text-xs px-2 py-0.5',
  md: 'text-sm px-2.5 py-1',
}

export function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const colorClass = colorMap[status] ?? 'bg-iskander-800 text-iskander-400'
  const sizeClass  = sizeMap[size]
  const label      = status.charAt(0).toUpperCase() + status.slice(1)

  return (
    <span className={`rounded-full font-medium ${sizeClass} ${colorClass}`}>
      {label}
    </span>
  )
}
