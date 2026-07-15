import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePositions, useUploadPosition, useSyncZohoPositions } from './hooks/usePositions'
import ManualPositionForm from './ManualPositionForm'


const STATUS_STYLES: Record<string, string> = {
  DRAFT: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  OPEN: 'bg-green-500/10 text-green-400 border-green-500/20',
  CLOSED: 'bg-zinc-800 text-zinc-400 border-zinc-700',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border ${STATUS_STYLES[status] ?? 'bg-zinc-800 text-zinc-400 border-zinc-700'}`}
    >
      {status}
    </span>
  )
}

export default function PositionsPage() {
  const navigate = useNavigate()
  const { data: positions = [], isLoading, isError } = usePositions()
  const upload = useUploadPosition()
  const syncZoho = useSyncZohoPositions()

  const [searchQuery, setSearchQuery] = useState('')
  const [syncError, setSyncError] = useState('')

  const [uploadOpen, setUploadOpen] = useState(false)
  const [slideOverOpen, setSlideOverOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadError, setUploadError] = useState('')
  const [uploadSuccess, setUploadSuccess] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (f) {
      setSelectedFile(f)
      setUploadError('')
    }
  }

  async function handleUpload() {
    if (!selectedFile) return
    setUploadError('')
    setUploadSuccess('')
    upload.mutate(selectedFile, {
      onSuccess: (data) => {
        setUploadSuccess(data.message)
        setSelectedFile(null)
        if (fileRef.current) fileRef.current.value = ''
        setTimeout(() => {
          setUploadOpen(false)
          setUploadSuccess('')
        }, 2000)
      },
      onError: (err: unknown) => {
        const msg =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          'Upload failed.'
        setUploadError(msg)
      },
    })
  }

  const filteredPositions = positions.filter((p) => {
    if (!searchQuery) return true
    const q = searchQuery.toLowerCase()
    return (
      (p.title && p.title.toLowerCase().includes(q)) ||
      (p.department && p.department.toLowerCase().includes(q))
    )
  })

  return (
    <div className="animate-fade-in w-full max-w-[1400px] mx-auto min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">Open Positions</h1>
        <div className="flex gap-3">
          <div className="flex flex-col items-end gap-1">
            <button
              onClick={() => {
                setSyncError('')
                syncZoho.mutate(undefined, {
                  onError: () => {
                    setSyncError('Failed to sync positions from Zoho.')
                  }
                })
              }}
              disabled={syncZoho.isPending}
              className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-4 py-2 text-sm font-medium text-indigo-400 hover:bg-indigo-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {syncZoho.isPending ? (
                <div className="flex items-center gap-2">
                  <svg className="h-4 w-4 animate-spin text-indigo-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Fetching...
                </div>
              ) : (
                'Fetch Positions'
              )}
            </button>
            {syncError && <span className="text-xs text-red-400">{syncError}</span>}
          </div>
          <button
            onClick={() => setUploadOpen(true)}
            className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-4 py-2 text-sm font-medium text-indigo-400 hover:bg-indigo-500/20 transition-colors shadow-sm"
          >
            Upload JD
          </button>
          <button
            onClick={() => setSlideOverOpen(true)}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-indigo-900/50 hover:bg-indigo-500 transition-colors"
          >
            + Create Manual
          </button>
        </div>
      </div>

      {/* Search Bar */}
      <div className="mb-6 glass-panel rounded-xl p-4 animate-slide-up animate-stagger-1">
        <input
          type="text"
          placeholder="Search positions by title or department..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full max-w-md rounded-lg border border-zinc-700 bg-zinc-950/50 px-4 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-colors"
        />
      </div>

      {/* Table */}
      {isLoading && (
        <div className="flex items-center gap-3 py-8 px-4 justify-center text-zinc-500 glass-panel rounded-xl animate-slide-up animate-stagger-2">
          <svg className="h-6 w-6 animate-spin text-indigo-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span className="text-sm font-medium">Loading positions…</span>
        </div>
      )}
      {isError && <p className="text-red-400 text-sm glass-panel p-4 rounded-xl">Failed to load positions.</p>}
      {!isLoading && !isError && positions.length === 0 && (
        <p className="text-zinc-500 text-sm glass-panel p-8 text-center rounded-xl animate-slide-up animate-stagger-2">No positions yet. Upload a JD or create one manually.</p>
      )}
      {!isLoading && !isError && positions.length > 0 && filteredPositions.length === 0 && (
        <p className="text-zinc-500 text-sm glass-panel p-8 text-center rounded-xl animate-slide-up animate-stagger-2">No positions match your search.</p>
      )}

      {positions.length > 0 && (
        <div className="overflow-hidden rounded-xl glass-panel animate-slide-up animate-stagger-2">
          <table className="min-w-full divide-y divide-zinc-800">
            <thead className="bg-zinc-900">
              <tr>
                {['Title', 'Department', 'Status', 'Candidates Required', 'Created'].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-wider text-zinc-400"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800 bg-zinc-950/30">
              {filteredPositions.map((p) => {
                const isProcessing = p.status === 'EXTRACTED' || p.status === 'STRUCTURED'
                if (isProcessing) {
                  return (
                    <tr key={p.id} className="animate-pulse bg-indigo-500/5">
                      <td colSpan={5} className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <svg className="h-5 w-5 animate-spin text-indigo-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          <span className="text-sm font-semibold text-indigo-400">Fetching Job.....</span>
                        </div>
                      </td>
                    </tr>
                  )
                }
                return (
                  <tr
                    key={p.id}
                    onClick={() => navigate(`/positions/${p.id}`)}
                    className="cursor-pointer hover:bg-zinc-800/80 transition-colors group"
                  >
                    <td className="px-4 py-4 text-sm font-medium text-zinc-100 group-hover:text-indigo-400 transition-colors">
                      {p.title ?? <span className="italic text-zinc-500">Processing…</span>}
                    </td>
                    <td className="px-4 py-4 text-sm text-zinc-400">{p.department ?? '—'}</td>
                    <td className="px-4 py-4">
                      <StatusBadge status={p.position_status} />
                    </td>
                    <td className="px-4 py-4 text-sm text-zinc-400 text-center">
                      {p.candidates_required ?? '—'}
                    </td>
                    <td className="px-4 py-4 text-sm text-zinc-500">
                      {new Date(p.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Upload JD Modal */}
      {uploadOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md rounded-2xl glass-panel p-6 shadow-2xl animate-slide-up border-zinc-700">
            <h2 className="text-lg font-semibold text-zinc-100 mb-4">Upload Job Description PDF</h2>

            <label className="block mb-4">
              <span className="text-sm font-medium text-zinc-400 mb-1 block">PDF file</span>
              <input
                ref={fileRef}
                type="file"
                accept="application/pdf"
                onChange={handleFileChange}
                className="block w-full text-sm text-zinc-400 file:mr-4 file:rounded-lg file:border border-indigo-500/20 file:bg-indigo-500/10 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-indigo-400 hover:file:bg-indigo-500/20 transition-colors"
              />
            </label>

            {uploadError && (
              <p className="text-sm text-red-400 mb-3">{uploadError}</p>
            )}
            {uploadSuccess && (
              <p className="text-sm text-green-400 mb-3">{uploadSuccess}</p>
            )}

            <div className="flex justify-end gap-3 mt-4">
              <button
                onClick={() => { setUploadOpen(false); setSelectedFile(null); setUploadError(''); setUploadSuccess('') }}
                className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
              >
                Cancel
              </button>
              <button
                disabled={!selectedFile || upload.isPending}
                onClick={handleUpload}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg transition-colors"
              >
                {upload.isPending ? 'Uploading…' : 'Upload'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Manual Slide-over */}
      {slideOverOpen && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm animate-fade-in" onClick={() => setSlideOverOpen(false)} />
          <div className="relative w-full max-w-xl bg-zinc-900 border-l border-zinc-800 shadow-2xl flex flex-col overflow-y-auto animate-fade-in">
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
              <h2 className="text-lg font-semibold text-zinc-100">Create Position Manually</h2>
              <button
                onClick={() => setSlideOverOpen(false)}
                className="text-zinc-500 hover:text-zinc-300 text-2xl font-bold transition-colors"
              >
                ×
              </button>
            </div>
            <div className="flex-1 px-6 py-4">
              <ManualPositionForm onClose={() => setSlideOverOpen(false)} />
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
