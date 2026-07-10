import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'
import {
  useCandidates,
  useSources,
  useDeleteCandidate,
  useDeleteCandidatesBulk,
  useClearPendingImports,
  useCandidateConflicts,
  useCandidateImports,
  useResolveConflict,
  useDismissImport,
  useSyncZohoCandidates,
  useZohoJobs,
  type CandidateConflict,
  type CandidateImport,
} from './hooks/useSources'

const SOURCE_STYLES: Record<string, string> = {
  local_kb: 'bg-blue-100 text-blue-800',
  github: 'bg-gray-800 text-white',
  zoho_forms: 'bg-purple-100 text-purple-800',
}

function SourceBadge({ source }: { source: string }) {
  const style = SOURCE_STYLES[source] ?? 'bg-gray-100 text-gray-700'
  const label = source.replace(/_/g, ' ')
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${style}`}>
      {label}
    </span>
  )
}

function ConflictCard({
  conflict,
  onResolve,
  resolving,
}: {
  conflict: CandidateConflict
  onResolve: (importId: string, action: 'update' | 'keep') => void
  resolving: boolean
}) {
  const proposed = conflict.proposed
  const existing = conflict.existing

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 space-y-4">
      <div>
        <p className="text-sm font-semibold text-amber-900">
          Duplicate email: {conflict.proposed_email}
        </p>
        <p className="text-xs text-amber-700 mt-1">
          A candidate with this email already exists. Choose whether to update with the new data from{' '}
          <SourceBadge source={conflict.source_name} /> or keep the existing record.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <div className="rounded-lg bg-white border border-gray-200 p-4">
          <p className="text-xs font-semibold uppercase text-gray-500 mb-2">Existing</p>
          <p className="text-sm font-medium text-gray-900">{existing.name ?? '—'}</p>
          <p className="text-xs text-gray-600">{existing.current_title ?? '—'}</p>
          <p className="text-xs text-gray-500 mt-1">{existing.summary?.slice(0, 120) ?? '—'}…</p>
        </div>
        <div className="rounded-lg bg-white border border-gray-200 p-4">
          <p className="text-xs font-semibold uppercase text-gray-500 mb-2">Incoming</p>
          <p className="text-sm font-medium text-gray-900">{(proposed.candidate_name as string) ?? '—'}</p>
          <p className="text-xs text-gray-600">{(proposed.current_title as string) ?? '—'}</p>
          <p className="text-xs text-gray-500 mt-1">{((proposed.summary as string) ?? '').slice(0, 120)}…</p>
        </div>
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => onResolve(conflict.import_id, 'update')}
          disabled={resolving}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
        >
          Update existing
        </button>
        <button
          onClick={() => onResolve(conflict.import_id, 'keep')}
          disabled={resolving}
          className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
        >
          Keep existing
        </button>
      </div>
    </div>
  )
}

function FailedImportCard({
  item,
  onDismiss,
  dismissing,
}: {
  item: CandidateImport
  onDismiss: (importId: string) => void
  dismissing: boolean
}) {
  const label =
    item.name ??
    (item.extracted_data?.candidate_name as string | undefined) ??
    'Uploaded CV'

  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex items-start justify-between gap-4">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-red-900">{label}</p>
        <p className="text-xs text-red-700 mt-1">
          Processing failed{item.source_name ? (
            <> from <SourceBadge source={item.source_name} /></>
          ) : null}
        </p>
        <p className="text-sm text-red-800 mt-2">
          {item.error_message ?? 'An unknown error occurred during processing.'}
        </p>
      </div>
      <button
        onClick={() => onDismiss(item.import_id)}
        disabled={dismissing}
        className="shrink-0 rounded-lg border border-red-300 bg-white px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-100 disabled:opacity-50"
      >
        Dismiss
      </button>
    </div>
  )
}

export default function CandidatesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: sources = [] } = useSources()

  const [sourceFilter, setSourceFilter] = useState('')
  const [nameSearch, setNameSearch] = useState('')

  const { data: candidates = [], isLoading, isError } = useCandidates(sourceFilter || undefined)
  const { data: conflicts = [] } = useCandidateConflicts()
  const { data: imports = [] } = useCandidateImports()
  const { data: zohoJobs = [], isLoading: isLoadingJobs } = useZohoJobs()

  const [isJobModalOpen, setIsJobModalOpen] = useState(false)
  const [selectedJobs, setSelectedJobs] = useState<string[]>([])

  const deleteCandidate = useDeleteCandidate()
  const deleteCandidatesBulk = useDeleteCandidatesBulk()
  const clearPendingImports = useClearPendingImports()
  const resolveConflict = useResolveConflict()
  const dismissImport = useDismissImport()
  const syncZohoCandidates = useSyncZohoCandidates()

  const processingCount = imports.filter((i) => i.status === 'PROCESSING').length
  const failedImports = imports.filter((i) => i.status === 'FAILED')

  function handleDelete(e: React.MouseEvent, email: string, candidateName: string | null) {
    e.stopPropagation()
    const label = candidateName ?? email
    if (!window.confirm(`Delete ${label} permanently? This cannot be undone.`)) return
    deleteCandidate.mutate(email)
  }

  function handleResolve(importId: string, action: 'update' | 'keep') {
    resolveConflict.mutate({ importId, action })
  }

  function handleDismiss(importId: string) {
    dismissImport.mutate(importId)
  }

  function handleDeleteAllZoho() {
    const count = candidates.filter((c) => c.source_name === 'zoho').length
    if (!window.confirm(`Delete all ${count} Zoho candidates permanently? This cannot be undone.`)) return
    deleteCandidatesBulk.mutate('zoho', {
      onSuccess: (data) => setUploadMessage(data.message),
      onError: () => setUploadError('Failed to delete Zoho candidates.'),
    })
  }

  function handleClearQueue() {
    clearPendingImports.mutate(undefined, {
      onSuccess: (data) => setUploadMessage(`Cleared ${data.cleared_count} stuck pending imports.`),
      onError: () => setUploadError('Failed to clear pending imports.'),
    })
  }

  // Upload CV
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    if (files.length === 0) return
    e.target.value = ''
    setUploadMessage(null)
    setUploadError(null)
    setUploading(true)
    try {
      const results = await Promise.allSettled(
        files.map(async (file) => {
          const form = new FormData()
          form.append('file', file)
          await api.post('/candidates/upload', form, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
        }),
      )
      const succeeded = results.filter((r) => r.status === 'fulfilled').length
      const failed = results.length - succeeded

      if (succeeded > 0) {
        setUploadMessage(
          succeeded === 1
            ? 'CV uploaded — processing in background'
            : `${succeeded} CVs uploaded — processing in background`,
        )
        queryClient.invalidateQueries({ queryKey: ['candidates'] })
        queryClient.invalidateQueries({ queryKey: ['candidate-imports'] })
        queryClient.invalidateQueries({ queryKey: ['candidate-conflicts'] })
      }
      if (failed > 0) {
        const firstFailure = results.find((r) => r.status === 'rejected') as PromiseRejectedResult | undefined
        const detail =
          (firstFailure?.reason as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          'Upload failed. Please try again.'
        setUploadError(
          failed === files.length
            ? detail
            : `${failed} of ${files.length} uploads failed. ${detail}`,
        )
      }
    } finally {
      setUploading(false)
    }
  }

  const filtered = candidates.filter((c) => {
    const term = nameSearch.toLowerCase()
    if (!term) return true
    return (
      (c.name ?? '').toLowerCase().includes(term) ||
      c.email.toLowerCase().includes(term)
    )
  })

  return (
    <div className="w-full min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-gray-900">Candidates</h1>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {uploading ? 'Uploading…' : 'Upload CV'}
          </button>
          <button
            onClick={() => setIsJobModalOpen(true)}
            disabled={syncZohoCandidates.isPending || uploading}
            className="inline-flex items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {syncZohoCandidates.isPending ? 'Syncing…' : 'Sync Zoho Candidates'}
          </button>
          <button
            onClick={handleDeleteAllZoho}
            disabled={deleteCandidatesBulk.isPending || candidates.filter(c => c.source_name === 'zoho').length === 0}
            className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {deleteCandidatesBulk.isPending ? 'Deleting…' : 'Delete All Zoho'}
          </button>
        </div>
        <span className="text-sm text-gray-400">{filtered.length} candidate{filtered.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Job Selection Modal */}
      {isJobModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 max-h-[80vh] flex flex-col">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Select Zoho Jobs to Sync</h2>
            <p className="text-sm text-gray-600 mb-4">
              Choose which job openings you want to extract candidates from. If none are selected, all candidates will be synced.
            </p>
            
            <div className="flex-1 overflow-y-auto border border-gray-200 rounded-lg p-2 space-y-2 mb-4">
              {isLoadingJobs ? (
                <p className="text-sm text-gray-500 p-2">Loading jobs...</p>
              ) : zohoJobs.length === 0 ? (
                <p className="text-sm text-gray-500 p-2">No active jobs found in Zoho.</p>
              ) : (
                zohoJobs.map(job => (
                  <label key={job.id} className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded cursor-pointer">
                    <input 
                      type="checkbox"
                      className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      checked={selectedJobs.includes(job.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedJobs(prev => [...prev, job.id])
                        } else {
                          setSelectedJobs(prev => prev.filter(id => id !== job.id))
                        }
                      }}
                    />
                    <span className="text-sm font-medium text-gray-900">
                      {job.Posting_Title || job.Job_Opening_Name || `Job ${job.id}`}
                    </span>
                  </label>
                ))
              )}
            </div>

            <div className="flex justify-end gap-3 mt-auto">
              <button
                onClick={() => {
                  setIsJobModalOpen(false)
                  setSelectedJobs([])
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setIsJobModalOpen(false)
                  setUploadMessage(null)
                  setUploadError(null)
                  syncZohoCandidates.mutate(selectedJobs, {
                    onSuccess: (data) => setUploadMessage(data.message),
                    onError: () => setUploadError("Failed to sync Zoho candidates.")
                  })
                  setSelectedJobs([])
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg"
              >
                Start Sync
              </button>
            </div>
          </div>
        </div>
      )}

      {processingCount > 0 && (
        <div className="mb-4 rounded-lg bg-blue-50 border border-blue-200 px-4 py-2 text-sm text-blue-700 flex items-center justify-between">
          <span>{processingCount} CV{processingCount !== 1 ? 's' : ''} processing in background…</span>
          <button
            onClick={handleClearQueue}
            disabled={clearPendingImports.isPending}
            className="ml-4 text-xs font-medium text-blue-600 hover:text-blue-800 underline disabled:opacity-50"
          >
            {clearPendingImports.isPending ? 'Clearing…' : 'Clear queue'}
          </button>
        </div>
      )}

      {failedImports.length > 0 && (
        <div className="mb-6 space-y-3">
          <h2 className="text-sm font-semibold text-red-900 uppercase tracking-wide">
            Processing failed ({failedImports.length})
          </h2>
          {failedImports.map((item) => (
            <FailedImportCard
              key={item.import_id}
              item={item}
              onDismiss={handleDismiss}
              dismissing={dismissImport.isPending}
            />
          ))}
        </div>
      )}

      {conflicts.length > 0 && (
        <div className="mb-6 space-y-4">
          <h2 className="text-sm font-semibold text-amber-900 uppercase tracking-wide">
            Duplicate emails — action required ({conflicts.length})
          </h2>
          {conflicts.map((conflict) => (
            <ConflictCard
              key={conflict.import_id}
              conflict={conflict}
              onResolve={handleResolve}
              resolving={resolveConflict.isPending}
            />
          ))}
        </div>
      )}

      {uploadMessage && (
        <div className="mb-4 rounded-lg bg-green-50 border border-green-200 px-4 py-2 text-sm text-green-700">
          {uploadMessage}
        </div>
      )}
      {uploadError && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">
          {uploadError}
        </div>
      )}

      {/* Filter bar */}
      <div className="flex gap-3 mb-5">
        <input
          type="text"
          placeholder="Search by name or email…"
          value={nameSearch}
          onChange={(e) => setNameSearch(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="">All sources</option>
          {sources.map((s) => (
            <option key={s.name} value={s.name}>
              {s.display_name}
            </option>
          ))}
        </select>
      </div>

      {isLoading && <p className="text-gray-500 text-sm">Loading candidates…</p>}
      {isError && <p className="text-red-500 text-sm">Failed to load candidates.</p>}
      {!isLoading && !isError && filtered.length === 0 && (
        <p className="text-gray-400 text-sm">No candidates match your filters.</p>
      )}

      {filtered.length > 0 && (
        <div className="w-full min-w-0 overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="w-full min-w-[960px] divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {['Name', 'Email', 'Current Title', 'Location', 'Source', 'Experience', 'Status', ''].map((h) => (
                  <th
                    key={h || 'actions'}
                    className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 whitespace-nowrap${
                      h === '' ? ' sticky right-0 bg-gray-50 z-10 text-right' : ''
                    }`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((c) => (
                <tr
                  key={c.email}
                  onClick={() => navigate(`/candidates/${encodeURIComponent(c.email)}`)}
                  className="group cursor-pointer hover:bg-indigo-50 transition-colors"
                >
                  <td className="px-4 py-3 text-sm font-medium text-gray-900 whitespace-nowrap">
                    {c.name ?? <span className="italic text-gray-400">Processing…</span>}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                    {c.email}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                    {c.current_title ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                    {c.location ?? '—'}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <SourceBadge source={c.source_name} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                    {c.years_experience != null ? `${c.years_experience} yrs` : '—'}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 font-medium uppercase whitespace-nowrap">
                    {c.status}
                  </td>
                  <td className="sticky right-0 z-10 bg-white px-4 py-3 text-right whitespace-nowrap group-hover:bg-indigo-50">
                    <button
                      onClick={(e) => handleDelete(e, c.email, c.name)}
                      disabled={deleteCandidate.isPending}
                      className="rounded-md border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700 hover:bg-red-100 disabled:opacity-50 transition-colors"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
