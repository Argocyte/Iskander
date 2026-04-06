'use client'

import { useState, useRef } from 'react'
import { SubGroup } from '@/types'
import { SubGroupFilter } from './SubGroupFilter'

interface ThreadFiltersProps {
  filters: { status?: string; tag?: string; sub_group_id?: string; search?: string }
  onFiltersChange: (filters: { status?: string; tag?: string; sub_group_id?: string; search?: string }) => void
  subGroups: SubGroup[]
  subGroupsLoading?: boolean
}

const STATUS_TABS = [
  { label: 'All',    value: undefined   },
  { label: 'Open',   value: 'open'      },
  { label: 'Closed', value: 'closed'    },
  { label: 'Pinned', value: 'pinned'    },
] as const

const tabBase     = 'px-3 py-1.5 rounded-lg text-sm font-medium cursor-pointer transition-colors'
const tabActive   = 'bg-iskander-700 text-iskander-100'
const tabInactive = 'bg-iskander-900 text-iskander-400 hover:bg-iskander-800'

export function ThreadFilters({
  filters,
  onFiltersChange,
  subGroups,
  subGroupsLoading = false,
}: ThreadFiltersProps) {
  const [searchInput, setSearchInput] = useState(filters.search ?? '')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  function handleStatusClick(value: string | undefined) {
    onFiltersChange({ ...filters, status: value })
  }

  function handleSearchChange(e: React.ChangeEvent<HTMLInputElement>) {
    const val = e.target.value
    setSearchInput(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      onFiltersChange({ ...filters, search: val || undefined })
    }, 300)
  }

  function handleSubGroupChange(id: string | null) {
    onFiltersChange({ ...filters, sub_group_id: id ?? undefined })
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Row 1: status tabs + search */}
      <div className="flex flex-col md:flex-row md:items-center gap-3">
        {/* Status tabs */}
        <div className="flex flex-wrap gap-1.5">
          {STATUS_TABS.map(tab => {
            const isActive = filters.status === tab.value
            return (
              <button
                key={tab.label}
                className={`${tabBase} ${isActive ? tabActive : tabInactive}`}
                onClick={() => handleStatusClick(tab.value)}
              >
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Search input */}
        <input
          type="text"
          value={searchInput}
          onChange={handleSearchChange}
          placeholder="Search threads..."
          className="bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none w-full"
        />
      </div>

      {/* Row 2: SubGroupFilter */}
      {!subGroupsLoading && subGroups.length > 0 && (
        <SubGroupFilter
          subGroups={subGroups}
          selectedId={filters.sub_group_id ?? null}
          onChange={handleSubGroupChange}
        />
      )}
    </div>
  )
}
