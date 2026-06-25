import { useState } from 'react'
import { usePositions } from '../positions/hooks/usePositions'
import { useSources } from '../candidates/hooks/useSources'
import { useMatches, useRecompute } from './hooks/useMatches'
import MatchResultsList from './MatchResultsList'

export default function MatchesPage() {
  const { data: positions = [] } = usePositions('OPEN')
  const { data: sources = [] } = useSources()

  const [selectedPosition, setSelectedPosition] = useState('')
  const [topK, setTopK] = useState(10)
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [runEnabled, setRunEnabled] = useState(false)

  const recompute = useRecompute()

  const { data: matchResult, isFetching, isError, refetch } = useMatches(
    selectedPosition,
    topK,
    selectedSources.length > 0 ? selectedSources : undefined,
    runEnabled,
  )

  const selectedPositionData = positions.find((p) => p.id === selectedPosition)

  function handleSourceToggle(name: string) {
    setSelectedSources((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name],
    )
  }

  function handleRunMatching() {
    if (!selectedPosition) return
    // Force a fresh recompute, then load results
    recompute.mutate(
      {
        job_id: selectedPosition,
        source_filter: selectedSources.length > 0 ? selectedSources : null,
        top_k: topK,
      },
      {
        onSuccess: () => {
          // Give background task a moment, then fetch
          setTimeout(() => {
            setRunEnabled(true)
            refetch()
          }, 1500)
        },
      },
    )
    // Also immediately try to load any cached results
    setRunEnabled(true)
  }

  const isRunning = recompute.isPending || isFetching

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Matching</h1>

      <div className="flex gap-6">
        {/* ── Left panel: controls ──────────────────────────────────────────── */}
        <aside className="w-64 flex-shrink-0 space-y-5">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-5">

            {/* Position selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Position
              </label>
              {positions.length === 0 ? (
                <p className="text-xs text-gray-400">No open positions. Approve one first.</p>
              ) : (
                <select
                  value={selectedPosition}
                  onChange={(e) => {
                    setSelectedPosition(e.target.value)
                    setRunEnabled(false)
                  }}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">— Select position —</option>
                  {positions.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.title ?? p.id}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Top K slider */}
            <div>
              <label className="flex items-center justify-between text-sm font-medium text-gray-700 mb-1">
                <span>Top K results</span>
                <span className="text-indigo-600 font-bold">{topK}</span>
              </label>
              <input
                type="range"
                min={5}
                max={50}
                step={5}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-full accent-indigo-600"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-0.5">
                <span>5</span>
                <span>50</span>
              </div>
            </div>

            {/* Source filter */}
            {sources.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Source filter</p>
                <div className="space-y-1.5">
                  {sources.map((s) => (
                    <label key={s.name} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedSources.includes(s.name)}
                        onChange={() => handleSourceToggle(s.name)}
                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="text-sm text-gray-700">{s.display_name}</span>
                    </label>
                  ))}
                </div>
                {selectedSources.length > 0 && (
                  <button
                    onClick={() => setSelectedSources([])}
                    className="mt-1.5 text-xs text-gray-400 hover:text-gray-600"
                  >
                    Clear selection
                  </button>
                )}
              </div>
            )}

            {/* Run button */}
            <button
              disabled={!selectedPosition || isRunning}
              onClick={handleRunMatching}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isRunning ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Running…
                </span>
              ) : (
                'Run Matching'
              )}
            </button>
          </div>

          {/* Score legend */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Score Legend</p>
            <div className="space-y-1.5 text-xs text-gray-600">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-indigo-500 flex-shrink-0" />
                Rule-based score
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-sky-400 flex-shrink-0" />
                Vector similarity
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-violet-500 flex-shrink-0" />
                LLM re-rank score
              </div>
            </div>
          </div>
        </aside>

        {/* ── Right panel: results ──────────────────────────────────────────── */}
        <div className="flex-1 min-w-0">
          {!selectedPosition && (
            <div className="h-64 flex items-center justify-center rounded-xl border-2 border-dashed border-gray-200">
              <p className="text-gray-400 text-sm">Select a position and click Run Matching</p>
            </div>
          )}

          {selectedPosition && !runEnabled && !matchResult && (
            <div className="h-64 flex items-center justify-center rounded-xl border-2 border-dashed border-indigo-100">
              <p className="text-indigo-400 text-sm">Click "Run Matching" to see results</p>
            </div>
          )}

          {isError && (
            <div className="rounded-xl bg-red-50 border border-red-200 p-4">
              <p className="text-sm text-red-600">
                Matching failed. Make sure the position has embedded candidates.
              </p>
            </div>
          )}

          {recompute.isError && (
            <div className="rounded-xl bg-red-50 border border-red-200 p-4 mb-4">
              <p className="text-sm text-red-600">
                {(recompute.error as { response?: { data?: { detail?: string } } })?.response?.data
                  ?.detail ?? 'Recompute request failed.'}
              </p>
            </div>
          )}

          {matchResult && selectedPositionData && (
            <MatchResultsList
              result={matchResult}
              positionTitle={selectedPositionData.title ?? selectedPosition}
              topK={topK}
            />
          )}
        </div>
      </div>
    </div>
  )
}
