import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePositions, useUploadPosition } from './hooks/usePositions'
import ManualPositionForm from './ManualPositionForm'

const STATUS_STYLES: Record<string, string> = {
  DRAFT: 'bg-yellow-100 text-yellow-800',
  OPEN: 'bg-green-100 text-green-800',
  CLOSED: 'bg-gray-100 text-gray-700',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600'}`}
    >
      {status}
    </span>
  )
}

export default function PositionsPage() {
  const navigate = useNavigate()
  const { data: positions = [], isLoading, isError } = usePositions()
  const upload = useUploadPosition()

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

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Open Positions</h1>
        <div className="flex gap-3">
          <button
            onClick={() => setUploadOpen(true)}
            className="rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-100 transition-colors"
          >
            Upload JD
          </button>
          <button
            onClick={() => setSlideOverOpen(true)}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors"
          >
            + Create Manual
          </button>
        </div>
      </div>

      {/* Table */}
      {isLoading && <p className="text-gray-500 text-sm">Loading positions…</p>}
      {isError && <p className="text-red-500 text-sm">Failed to load positions.</p>}
      {!isLoading && !isError && positions.length === 0 && (
        <p className="text-gray-400 text-sm">No positions yet. Upload a JD or create one manually.</p>
      )}

      {positions.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {['Title', 'Department', 'Status', 'Candidates Required', 'Created'].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {positions.map((p) => (
                <tr
                  key={p.id}
                  onClick={() => navigate(`/positions/${p.id}`)}
                  className="cursor-pointer hover:bg-indigo-50 transition-colors"
                >
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {p.title ?? <span className="italic text-gray-400">Processing…</span>}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{p.department ?? '—'}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={p.position_status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 text-center">
                    {p.candidates_required ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(p.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Upload JD Modal */}
      {uploadOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Job Description PDF</h2>

            <label className="block mb-4">
              <span className="text-sm font-medium text-gray-700 mb-1 block">PDF file</span>
              <input
                ref={fileRef}
                type="file"
                accept="application/pdf"
                onChange={handleFileChange}
                className="block w-full text-sm text-gray-500 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-indigo-700 hover:file:bg-indigo-100"
              />
            </label>

            {uploadError && (
              <p className="text-sm text-red-600 mb-3">{uploadError}</p>
            )}
            {uploadSuccess && (
              <p className="text-sm text-green-600 mb-3">{uploadSuccess}</p>
            )}

            <div className="flex justify-end gap-3 mt-2">
              <button
                onClick={() => { setUploadOpen(false); setSelectedFile(null); setUploadError(''); setUploadSuccess('') }}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                disabled={!selectedFile || upload.isPending}
                onClick={handleUpload}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
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
          <div className="fixed inset-0 bg-black/30" onClick={() => setSlideOverOpen(false)} />
          <div className="relative w-full max-w-xl bg-white shadow-xl flex flex-col overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Create Position Manually</h2>
              <button
                onClick={() => setSlideOverOpen(false)}
                className="text-gray-400 hover:text-gray-600 text-xl font-bold"
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
