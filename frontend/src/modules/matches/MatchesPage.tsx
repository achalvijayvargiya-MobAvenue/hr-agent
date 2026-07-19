import { useState } from 'react'
import { usePositions } from '../positions/hooks/usePositions'
import { useSources } from '../candidates/hooks/useSources'
import { useMatches, useRecompute } from './hooks/useMatches'
import MatchResultsList from './MatchResultsList'
import { Select } from '../../components/ui/Select'

export default function MatchesPage() {
  const { data: positions = [] } = usePositions('OPEN')
  const { data: sources = [] } = useSources()

  const [selectedPosition, setSelectedPosition] = useState('')
  const [topK, setTopK] = useState(10)
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [runEnabled, setRunEnabled] = useState(false)
  const [isSourcesOpen, setIsSourcesOpen] = useState(false)

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
    <div className="animate-fade-in w-full max-w-[1400px] mx-auto min-w-0">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-white">Matching</h1>
        <p className="text-sm text-zinc-400 mt-1">Run AI-powered matching to discover top candidates for open positions</p>
      </div>

      <div className="space-y-6">
        {/* ── Floating Glass Cards: controls ──────────────────────────────────────────── */}
        <div className="flex flex-wrap items-stretch gap-4 animate-slide-up animate-stagger-1 relative z-40">
          
          {/* Overlay for dropdown click-away */}
          {isSourcesOpen && (
            <div 
              className="fixed inset-0 z-40" 
              onClick={() => setIsSourcesOpen(false)} 
            />
          )}

          {/* Zone 1: Position */}
          <div className="flex-1 min-w-[280px] bg-white/5 backdrop-blur-2xl border border-white/10 border-b-black/50 border-r-black/50 rounded-2xl p-3 px-5 shadow-[0_8px_30px_rgba(0,0,0,0.6)] flex flex-col justify-center transition-all hover:bg-white/10 relative z-10">
            <div className="flex items-center gap-1.5 mb-1">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5 text-zinc-400">
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 0 0 .75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 0 0-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0 1 12 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 0 1-.673-.38m0 0A2.18 2.18 0 0 1 3 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 0 1 3.413-.387m7.5 0V5.25A2.25 2.25 0 0 0 13.5 3h-3a2.25 2.25 0 0 0-2.25 2.25v.894m7.5 0a48.667 48.667 0 0 0-7.5 0M12 12.75h.008v.008H12v-.008Z" />
              </svg>
              <label className="block text-[10px] font-bold text-zinc-400 uppercase tracking-[0.2em]">
                Position
              </label>
            </div>
            {positions.length === 0 ? (
              <p className="text-sm text-zinc-500 py-0.5">No open positions. Approve one first.</p>
            ) : (
              <Select
                value={selectedPosition}
                onChange={(value) => {
                  setSelectedPosition(value)
                  setRunEnabled(false)
                }}
                options={positions.map(p => ({ label: p.title ?? p.id, value: p.id }))}
                placeholder="— Select position —"
              />
            )}
          </div>

          {/* Zone 2: Sources */}
          {sources.length > 0 && (
            <div className="relative z-50">
              <div 
                className="w-[220px] h-full bg-white/5 backdrop-blur-2xl border border-white/10 border-b-black/50 border-r-black/50 rounded-2xl p-3 px-5 shadow-[0_8px_30px_rgba(0,0,0,0.6)] flex flex-col justify-center cursor-pointer transition-all hover:bg-white/10"
                onClick={() => setIsSourcesOpen(!isSourcesOpen)}
              >
                <div className="flex items-center gap-1.5 mb-1 pointer-events-none">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5 text-zinc-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
                  </svg>
                  <label className="block text-[10px] font-bold text-zinc-400 uppercase tracking-[0.2em]">
                    Sources
                  </label>
                </div>
                <div className="flex items-center justify-between text-base font-semibold text-white pointer-events-none">
                  <span>
                    {selectedSources.length === 0 
                      ? 'All Sources' 
                      : `${selectedSources.length} Selected`}
                  </span>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={`w-5 h-5 text-white transition-transform ${isSourcesOpen ? 'rotate-180' : ''}`}>
                    <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              
              {/* Dropdown Menu */}
              <div className={`absolute top-[calc(100%+12px)] left-0 w-full min-w-[240px] bg-zinc-900/95 backdrop-blur-xl border border-zinc-700 rounded-xl shadow-2xl p-2 transition-all transform origin-top-left ${isSourcesOpen ? 'opacity-100 scale-100' : 'opacity-0 scale-95 pointer-events-none'}`}>
                <div className="space-y-1">
                  {sources.map((s) => (
                    <label key={s.name} className="flex items-center gap-3 p-2.5 hover:bg-zinc-800/80 rounded-lg cursor-pointer transition-colors">
                      <input
                        type="checkbox"
                        checked={selectedSources.includes(s.name)}
                        onChange={() => handleSourceToggle(s.name)}
                        className="w-4 h-4 rounded border-zinc-600 bg-zinc-950 text-orange-500 focus:ring-orange-500 focus:ring-offset-zinc-900 cursor-pointer"
                      />
                      <span className="text-sm font-medium text-zinc-200">{s.display_name}</span>
                    </label>
                  ))}
                </div>
                {selectedSources.length > 0 && (
                  <button
                    onClick={() => {
                      setSelectedSources([])
                      setIsSourcesOpen(false)
                    }}
                    className="w-full mt-2 pt-2 pb-1 border-t border-zinc-800/50 text-xs font-semibold text-orange-400 hover:text-orange-300 transition-colors text-center uppercase tracking-wide"
                  >
                    Clear All
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Zone 3: Top K */}
          <div className="w-[180px] bg-white/5 backdrop-blur-2xl border border-white/10 border-b-black/50 border-r-black/50 rounded-2xl p-3 px-5 shadow-[0_8px_30px_rgba(0,0,0,0.6)] flex flex-col justify-center transition-all hover:bg-white/10 relative z-10">
            <div className="flex items-center gap-1.5 mb-1 pointer-events-none">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5 text-zinc-400">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75" />
              </svg>
              <label className="block text-[10px] font-bold text-zinc-400 uppercase tracking-[0.2em]">
                Limit
              </label>
            </div>
            <Select
              value={topK.toString()}
              onChange={(value) => setTopK(Number(value))}
              options={[
                { label: 'Show Top 5', value: '5' },
                { label: 'Show Top 10', value: '10' },
                { label: 'Show Top 20', value: '20' },
                { label: 'Show Top 50', value: '50' }
              ]}
            />
          </div>

          {/* Zone 4: Action */}
          <button
            disabled={!selectedPosition || isRunning}
            onClick={handleRunMatching}
            className="relative z-10 flex-shrink-0 h-auto py-3 px-8 flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-b from-orange-500 to-orange-600 text-sm font-bold text-white shadow-[0_8px_30px_rgba(234,88,12,0.4),inset_0_1px_1px_rgba(255,255,255,0.4)] hover:-translate-y-0.5 hover:shadow-[0_12px_40px_rgba(234,88,12,0.6),inset_0_1px_1px_rgba(255,255,255,0.5)] hover:from-orange-400 hover:to-orange-500 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none transition-all duration-300"
          >
            {isRunning ? (
              <>
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Running…
              </>
            ) : (
              <>
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09l2.846.813-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
                </svg>
                Run Matching
              </>
            )}
          </button>
        </div>

        {/* ── Bottom panel: results ──────────────────────────────────────────── */}
        <div className="animate-slide-up animate-stagger-2">
          {/* Inline score legend */}
          {(selectedPosition && matchResult && matchResult.matches.length > 0) && (
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 mb-4 px-1">
              <span className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Score Legend:</span>
              <div className="flex flex-wrap items-center gap-4 text-xs font-medium text-zinc-400">
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)]" />
                  Requirement Fit
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-2.5 h-2.5 rounded-full bg-sky-400 shadow-[0_0_6px_rgba(56,189,248,0.5)]" />
                  Semantic Match
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-2.5 h-2.5 rounded-full bg-orange-500 shadow-[0_0_6px_rgba(249,115,22,0.5)]" />
                  AI Assessment
                </span>
              </div>
            </div>
          )}

          {!selectedPosition && (
            <div className="h-64 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-zinc-800 bg-zinc-950/30 text-center px-4 mt-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-orange-500/10 text-orange-400 mb-4 border border-orange-500/20">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 15.75l-2.489-2.489m0 0a3.375 3.375 0 10-4.773-4.773 3.375 3.375 0 004.774 4.774zM21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-zinc-200 mb-1">Ready to Match</h3>
              <p className="text-zinc-500 text-sm max-w-[250px]">Select a position and configure your parameters above to discover top candidates.</p>
            </div>
          )}

          {selectedPosition && !runEnabled && !matchResult && (
            <div className="h-64 flex items-center justify-center rounded-xl border-2 border-dashed border-orange-500/30 bg-orange-500/5 mt-6">
              <p className="text-orange-400 text-sm">Click "Run Matching" to see results</p>
            </div>
          )}

          {isError && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 mb-4 mt-6">
              <p className="text-sm text-red-400">
                Matching failed. Make sure the position has embedded candidates.
              </p>
            </div>
          )}

          {recompute.isError && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 mb-4 mt-6">
              <p className="text-sm text-red-400">
                {(recompute.error as { response?: { data?: { detail?: string } } })?.response?.data
                  ?.detail ?? 'Recompute request failed.'}
              </p>
            </div>
          )}

          {matchResult && selectedPositionData && (
            <p className="text-xs text-zinc-500 mb-3 ml-1 mt-6">
              Matching runs on the domain pool only. Build the pool on the position page first.
            </p>
          )}

          {matchResult && selectedPositionData && (
            <div className="mt-6">
              <MatchResultsList
                result={matchResult}
                positionTitle={selectedPositionData.title ?? selectedPosition}
                topK={topK}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
