'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { deliberation } from '@/lib/api'
import { StanceResponse } from '@/types'

interface StanceFormProps {
  threadId: string
  proposalId: string
  processType: string
  options: string[] | null
  existingStance?: StanceResponse | null
  onStanceCast: (stance: StanceResponse) => void
}

const STANCE_PROCESSES = ['sense_check', 'advice', 'consent', 'consensus']
const BLOCK_PROCESSES  = ['consent', 'consensus']

const stanceButtons = [
  { key: 'agree',    label: 'Agree',    base: 'bg-green-900/50 border-green-700',   ring: 'ring-green-500' },
  { key: 'abstain',  label: 'Abstain',  base: 'bg-gray-800 border-gray-600',        ring: 'ring-gray-400' },
  { key: 'disagree', label: 'Disagree', base: 'bg-orange-900/50 border-orange-700', ring: 'ring-orange-500' },
  { key: 'block',    label: 'Block',    base: 'bg-red-900/50 border-red-700',       ring: 'ring-red-500' },
] as const

export function StanceForm({
  threadId,
  proposalId,
  processType,
  options,
  existingStance,
  onStanceCast,
}: StanceFormProps) {
  const { user, isAuthenticated } = useAuth()

  const [selectedStance, setSelectedStance] = useState<string>('')
  const [reason, setReason] = useState<string>('')
  const [scores, setScores] = useState<Record<string, number>>({})
  const [rankings, setRankings] = useState<string[]>([])
  const [selectedOptions, setSelectedOptions] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Pre-fill from existingStance
  useEffect(() => {
    if (!existingStance) return
    setSelectedStance(existingStance.stance)
    setReason(existingStance.reason ?? '')
    if (existingStance.score !== null) {
      // For score process, pre-fill scores from the stance value
      // The existing stance stores a single score; options need individual handling
    }
  }, [existingStance])

  // Initialize option-dependent state
  useEffect(() => {
    if (!options) return
    if (processType === 'score') {
      const initial: Record<string, number> = {}
      options.forEach((opt) => { initial[opt] = 5 })
      setScores(initial)
    }
    if (processType === 'rank') {
      setRankings([...options])
    }
    if (processType === 'allocate') {
      const initial: Record<string, number> = {}
      options.forEach((opt) => { initial[opt] = 0 })
      setScores(initial)
    }
  }, [options, processType])

  if (!isAuthenticated || !user) {
    return (
      <p className="text-iskander-500 text-sm italic">Sign in to vote</p>
    )
  }

  const isStanceBased = STANCE_PROCESSES.includes(processType)
  const isUpdate = !!existingStance

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      const body: {
        member_did: string
        stance: string
        reason?: string
        score?: number
        rank_order?: Record<string, unknown>[]
      } = {
        member_did: user!.did ?? user!.address,
        stance: selectedStance,
      }

      if (reason.trim()) body.reason = reason.trim()

      if (processType === 'score' && options) {
        // Send first score; backend may accept full map
        const firstOption = options[0]
        if (firstOption && scores[firstOption] !== undefined) {
          body.score = scores[firstOption]
        }
      }

      if (processType === 'rank') {
        body.rank_order = rankings.map((opt, idx) => ({ option: opt, position: idx + 1 }))
      }

      const result = await deliberation.castStance(threadId, proposalId, body)
      onStanceCast(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cast stance')
    } finally {
      setSubmitting(false)
    }
  }

  const allocateTotal = Object.values(scores).reduce((sum, v) => sum + v, 0)

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* ── Stance-based processes ───────────────────────────────────────── */}
      {isStanceBased && (
        <div className="space-y-2">
          <div className="flex gap-2 flex-wrap">
            {stanceButtons.map((btn) => {
              // Block only available for consent/consensus
              if (btn.key === 'block' && !BLOCK_PROCESSES.includes(processType)) {
                return null
              }
              const isSelected = selectedStance === btn.key
              return (
                <button
                  key={btn.key}
                  type="button"
                  onClick={() => setSelectedStance(btn.key)}
                  className={`px-4 py-2 rounded-lg border text-sm font-medium transition-all ${btn.base} ${
                    isSelected ? `ring-2 ring-offset-2 ring-offset-iskander-900 ${btn.ring}` : ''
                  }`}
                >
                  {btn.label}
                </button>
              )
            })}
          </div>
          {selectedStance === 'block' && (
            <p className="text-red-400 text-xs">Blocks prevent the proposal from passing</p>
          )}
        </div>
      )}

      {/* ── Choose process: radio list ───────────────────────────────────── */}
      {processType === 'choose' && options && (
        <div className="space-y-2">
          {options.map((opt) => (
            <label key={opt} className="flex items-center gap-2 text-iskander-300 text-sm cursor-pointer">
              <input
                type="radio"
                name="choose-option"
                value={opt}
                checked={selectedStance === opt}
                onChange={() => setSelectedStance(opt)}
                className="accent-iskander-500"
              />
              {opt}
            </label>
          ))}
        </div>
      )}

      {/* ── Score process: range sliders ──────────────────────────────────── */}
      {processType === 'score' && options && (
        <div className="space-y-3">
          {options.map((opt) => (
            <div key={opt} className="space-y-1">
              <div className="flex justify-between text-iskander-300 text-sm">
                <span>{opt}</span>
                <span className="text-iskander-400 font-mono">{scores[opt] ?? 5}</span>
              </div>
              <input
                type="range"
                min={0}
                max={10}
                value={scores[opt] ?? 5}
                onChange={(e) =>
                  setScores((prev) => ({ ...prev, [opt]: Number(e.target.value) }))
                }
                className="w-full accent-iskander-500"
              />
            </div>
          ))}
        </div>
      )}

      {/* ── Allocate process: number inputs ──────────────────────────────── */}
      {processType === 'allocate' && options && (
        <div className="space-y-2">
          {options.map((opt) => (
            <div key={opt} className="flex items-center gap-2">
              <span className="text-iskander-300 text-sm flex-1">{opt}</span>
              <input
                type="number"
                min={0}
                max={100}
                value={scores[opt] ?? 0}
                onChange={(e) =>
                  setScores((prev) => ({ ...prev, [opt]: Number(e.target.value) }))
                }
                className="w-20 bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
              />
            </div>
          ))}
          <p className={`text-xs ${allocateTotal === 100 ? 'text-green-400' : 'text-iskander-400'}`}>
            {100 - allocateTotal} points remaining
          </p>
        </div>
      )}

      {/* ── Rank process: orderable list ──────────────────────────────────── */}
      {processType === 'rank' && rankings.length > 0 && (
        <div className="space-y-1">
          {rankings.map((opt, idx) => (
            <div key={opt} className="flex items-center gap-2 bg-iskander-950 rounded-lg p-2 border border-iskander-800">
              <span className="text-iskander-400 text-xs w-6 text-center">{idx + 1}.</span>
              <span className="text-iskander-300 text-sm flex-1">{opt}</span>
              <button
                type="button"
                disabled={idx === 0}
                onClick={() => {
                  const next = [...rankings]
                  ;[next[idx - 1], next[idx]] = [next[idx], next[idx - 1]]
                  setRankings(next)
                }}
                className="text-iskander-500 hover:text-iskander-300 disabled:opacity-30 text-xs px-1"
              >
                &uarr;
              </button>
              <button
                type="button"
                disabled={idx === rankings.length - 1}
                onClick={() => {
                  const next = [...rankings]
                  ;[next[idx], next[idx + 1]] = [next[idx + 1], next[idx]]
                  setRankings(next)
                }}
                className="text-iskander-500 hover:text-iskander-300 disabled:opacity-30 text-xs px-1"
              >
                &darr;
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── Time poll process: checkboxes ─────────────────────────────────── */}
      {processType === 'time_poll' && options && (
        <div className="space-y-2">
          {options.map((opt) => (
            <label key={opt} className="flex items-center gap-2 text-iskander-300 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={selectedOptions.includes(opt)}
                onChange={(e) => {
                  setSelectedOptions((prev) =>
                    e.target.checked ? [...prev, opt] : prev.filter((o) => o !== opt)
                  )
                }}
                className="accent-iskander-500"
              />
              {opt}
            </label>
          ))}
        </div>
      )}

      {/* ── Reason textarea (always shown) ───────────────────────────────── */}
      <textarea
        rows={2}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Reason for your stance..."
        className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none resize-none"
      />

      {/* ── Error ────────────────────────────────────────────────────────── */}
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {/* ── Submit ───────────────────────────────────────────────────────── */}
      <button
        type="submit"
        disabled={submitting || (!selectedStance && processType !== 'time_poll' && processType !== 'score' && processType !== 'allocate' && processType !== 'rank')}
        className="bg-iskander-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-iskander-500 disabled:opacity-50 transition-colors"
      >
        {submitting ? 'Submitting\u2026' : isUpdate ? 'Update Vote' : 'Cast Vote'}
      </button>
    </form>
  )
}
