import { useState } from 'react'
import { useSources, useFetchCandidates } from '../candidates/hooks/useSources'
import { usePositions } from '../positions/hooks/usePositions'
import { Select } from '../../components/ui/Select'

interface Toast {
  message: string
  type: 'success' | 'error'
}

function AvailabilityDot({ available }: { available: boolean }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full ${available ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-zinc-600'}`}
      title={available ? 'Available' : 'Unavailable'}
    />
  )
}

export default function SourcesPage() {
  const { data: sources = [], isLoading } = useSources()
  const { data: positions = [] } = usePositions('OPEN')
  const fetchCandidates = useFetchCandidates()

  const [modalOpen, setModalOpen] = useState(false)
  const [selectedPosition, setSelectedPosition] = useState('')
  const [toast, setToast] = useState<Toast | null>(null)

  function showToast(message: string, type: Toast['type'] = 'success') {
    setToast({ message, type })
    setTimeout(() => setToast(null), 4000)
  }

  function handleFetch() {
    if (!selectedPosition) return
    fetchCandidates.mutate(selectedPosition, {
      onSuccess: (data) => {
        setModalOpen(false)
        setSelectedPosition('')
        showToast(`Queued ${data.new_candidates} new candidate(s) from ${data.sources_queried.join(', ')}.`)
      },
      onError: (err: unknown) => {
        const msg =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          'Failed to fetch candidates.'
        showToast(msg, 'error')
        setModalOpen(false)
      },
    })
  }

  return (
    <div className="animate-fade-in w-full max-w-[1400px] mx-auto min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">Candidate Sources</h1>
        <button
          onClick={() => setModalOpen(true)}
          className="rounded-lg bg-orange-600 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-orange-900/50 hover:bg-orange-500 transition-colors"
        >
          Fetch for Position
        </button>
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={`fixed top-5 right-5 z-50 rounded-xl px-5 py-3 shadow-lg text-sm font-medium transition-all ${
            toast.type === 'success'
              ? 'bg-green-600 text-white'
              : 'bg-red-600 text-white'
          }`}
        >
          {toast.message}
        </div>
      )}

      {/* Source Cards Grid */}
      {isLoading && <p className="text-zinc-500 text-sm glass-panel p-4 rounded-xl animate-slide-up animate-stagger-1">Loading sources…</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {sources.map((source, idx) => (
          <div
            key={source.name}
            className="glass-panel rounded-xl p-5 flex flex-col gap-3 animate-slide-up hover:-translate-y-1 transition-transform group"
            style={{ animationDelay: `${(idx + 1) * 100}ms` }}
          >
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-zinc-100 group-hover:text-orange-400 transition-colors">{source.display_name}</h2>
              <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                <AvailabilityDot available={source.is_available} />
                {source.is_available ? 'Available' : 'Unavailable'}
              </div>
            </div>
            <p className="text-xs text-zinc-500 font-mono bg-zinc-950/50 p-2 rounded-lg border border-zinc-800/50">{source.name}</p>
          </div>
        ))}

        {!isLoading && sources.length === 0 && (
          <p className="text-zinc-500 text-sm col-span-3 glass-panel p-8 text-center rounded-xl animate-slide-up animate-stagger-2">No sources registered.</p>
        )}
      </div>

      {/* Fetch for Position Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-md rounded-2xl glass-panel p-6 shadow-2xl animate-slide-up border-zinc-700">
            <h2 className="text-lg font-semibold text-zinc-100 mb-4">Select an Open Position</h2>

            {positions.length === 0 ? (
              <p className="text-sm text-zinc-400 mb-4">
                No open positions found. Approve a position first.
              </p>
            ) : (
              <Select
                value={selectedPosition}
                onChange={setSelectedPosition}
                options={[
                  { label: '— Choose a position —', value: '' },
                  ...positions.map((p) => ({
                    label: `${p.title ?? p.id} ${p.department ? `(${p.department})` : ''}`.trim(),
                    value: p.id
                  }))
                ]}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2.5 mb-4 transition-colors"
              />
            )}

            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setModalOpen(false); setSelectedPosition('') }}
                className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
              >
                Cancel
              </button>
              <button
                disabled={!selectedPosition || fetchCandidates.isPending}
                onClick={handleFetch}
                className="rounded-lg bg-orange-600 px-4 py-2 text-sm font-semibold text-white shadow-lg hover:bg-orange-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {fetchCandidates.isPending ? 'Fetching…' : 'Fetch Candidates'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
