import { useState } from 'react'
import { useSources, useFetchCandidates } from '../candidates/hooks/useSources'
import { usePositions } from '../positions/hooks/usePositions'

interface Toast {
  message: string
  type: 'success' | 'error'
}

function AvailabilityDot({ available }: { available: boolean }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full ${available ? 'bg-green-500' : 'bg-gray-300'}`}
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
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Candidate Sources</h1>
        <button
          onClick={() => setModalOpen(true)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors"
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
      {isLoading && <p className="text-gray-500 text-sm">Loading sources…</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {sources.map((source) => (
          <div
            key={source.name}
            className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-3"
          >
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">{source.display_name}</h2>
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <AvailabilityDot available={source.is_available} />
                {source.is_available ? 'Available' : 'Unavailable'}
              </div>
            </div>
            <p className="text-xs text-gray-400 font-mono">{source.name}</p>
          </div>
        ))}

        {!isLoading && sources.length === 0 && (
          <p className="text-gray-400 text-sm col-span-3">No sources registered.</p>
        )}
      </div>

      {/* Fetch for Position Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Select an Open Position</h2>

            {positions.length === 0 ? (
              <p className="text-sm text-gray-500 mb-4">
                No open positions found. Approve a position first.
              </p>
            ) : (
              <select
                value={selectedPosition}
                onChange={(e) => setSelectedPosition(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 mb-4"
              >
                <option value="">— Choose a position —</option>
                {positions.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title ?? p.id} {p.department ? `(${p.department})` : ''}
                  </option>
                ))}
              </select>
            )}

            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setModalOpen(false); setSelectedPosition('') }}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                disabled={!selectedPosition || fetchCandidates.isPending}
                onClick={handleFetch}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
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
