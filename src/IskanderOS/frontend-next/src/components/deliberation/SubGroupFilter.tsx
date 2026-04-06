import { SubGroup } from '@/types'

interface SubGroupFilterProps {
  subGroups: SubGroup[]
  selectedId: string | null
  onChange: (id: string | null) => void
}

const baseClass    = 'px-3 py-1 rounded-full text-sm cursor-pointer transition-colors'
const activeClass  = 'bg-iskander-700 text-iskander-100'
const inactiveClass = 'bg-iskander-900 text-iskander-400 hover:bg-iskander-800'

export function SubGroupFilter({ subGroups, selectedId, onChange }: SubGroupFilterProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        className={`${baseClass} ${selectedId === null ? activeClass : inactiveClass}`}
        onClick={() => onChange(null)}
      >
        All Groups
      </button>
      {subGroups.map(subGroup => (
        <button
          type="button"
          key={subGroup.id}
          className={`${baseClass} ${selectedId === subGroup.id ? activeClass : inactiveClass}`}
          onClick={() => onChange(subGroup.id)}
        >
          {subGroup.name}
        </button>
      ))}
    </div>
  )
}
