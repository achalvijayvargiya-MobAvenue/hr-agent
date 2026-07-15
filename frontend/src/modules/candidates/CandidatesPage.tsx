import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'
import {
  useCandidates,
  useSources,
  useDeleteCandidate,
  useCandidateConflicts,
  useCandidateImports,
  useResolveConflict,
  useDismissImport,
  useFetchCandidates,
  type CandidateConflict,
  type CandidateImport,
} from './hooks/useSources'
import { usePositions } from '../positions/hooks/usePositions'

const SOURCE_STYLES: Record<string, string> = {
  local_kb: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
  github: 'bg-zinc-800 text-zinc-300 border-zinc-700',
}

function SourceBadge({ source }: { source: string }) {
  const style = SOURCE_STYLES[source] ?? 'bg-zinc-800 text-zinc-400 border-zinc-700'
  const label = source.replace(/_/g, ' ')
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize border ${style}`}>
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
    <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-5 space-y-4">
      <div>
        <p className="text-sm font-semibold text-yellow-500">
          Duplicate email: {conflict.proposed_email}
        </p>
        <p className="text-xs text-yellow-200/70 mt-1">
          A candidate with this email already exists. Choose whether to update with the new data from{' '}
          <SourceBadge source={conflict.source_name} /> or keep the existing record.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <div className="rounded-lg bg-zinc-900/50 border border-zinc-800 p-4">
          <p className="text-xs font-semibold uppercase text-zinc-500 mb-2">Existing</p>
          <p className="text-sm font-medium text-zinc-100">{existing.name ?? '—'}</p>
          <p className="text-xs text-zinc-400">{existing.current_title ?? '—'}</p>
          <p className="text-xs text-zinc-500 mt-1">{existing.summary?.slice(0, 120) ?? '—'}…</p>
        </div>
        <div className="rounded-lg bg-zinc-900/50 border border-zinc-800 p-4">
          <p className="text-xs font-semibold uppercase text-zinc-500 mb-2">Incoming</p>
          <p className="text-sm font-medium text-zinc-100">{(proposed.candidate_name as string) ?? '—'}</p>
          <p className="text-xs text-zinc-400">{(proposed.current_title as string) ?? '—'}</p>
          <p className="text-xs text-zinc-500 mt-1">{((proposed.summary as string) ?? '').slice(0, 120)}…</p>
        </div>
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => onResolve(conflict.import_id, 'update')}
          disabled={resolving}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 disabled:opacity-60 transition-colors"
        >
          Update existing
        </button>
        <button
          onClick={() => onResolve(conflict.import_id, 'keep')}
          disabled={resolving}
          className="rounded-lg border border-zinc-700 bg-transparent px-4 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-800 disabled:opacity-60 transition-colors"
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
    <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 flex items-start justify-between gap-4">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-red-400">{label}</p>
        <p className="text-xs text-red-300/70 mt-1">
          Processing failed{item.source_name ? (
            <> from <SourceBadge source={item.source_name} /></>
          ) : null}
        </p>
        <p className="text-sm text-red-400/80 mt-2">
          {item.error_message ?? 'An unknown error occurred during processing.'}
        </p>
      </div>
      <button
        onClick={() => onDismiss(item.import_id)}
        disabled={dismissing}
        className="shrink-0 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-400 hover:bg-red-500/20 disabled:opacity-50 transition-colors"
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
  const { data: positions = [] } = usePositions()

  const [sourceFilter, setSourceFilter] = useState('')
  const [jobFilter, setJobFilter] = useState('')
  const [nameSearch, setNameSearch] = useState('')

  const { data: candidates = [], isLoading, isError } = useCandidates(
    sourceFilter || undefined,
    jobFilter || undefined
  )
  const { data: conflicts = [] } = useCandidateConflicts()
  const { data: imports = [] } = useCandidateImports()
  const deleteCandidate = useDeleteCandidate()
  const resolveConflict = useResolveConflict()
  const dismissImport = useDismissImport()

  const processingCount = imports.filter((i) => i.status === 'PROCESSING').length
  const failedImports = imports.filter((i) => i.status === 'FAILED')

  const fetchCandidates = useFetchCandidates()
  const [isFetchModalOpen, setIsFetchModalOpen] = useState(false)
  const [selectedPositionsForFetch, setSelectedPositionsForFetch] = useState<Set<string>>(new Set())

  function handleFetchClick() {
    setIsFetchModalOpen(true)
  }

  async function handleFetchSubmit() {
    if (selectedPositionsForFetch.size === 0) {
      alert("Please select at least one position.")
      return
    }
    const promises = Array.from(selectedPositionsForFetch).map(id => fetchCandidates.mutateAsync(id))
    try {
      await Promise.all(promises)
      alert("Candidates fetch triggered successfully for selected positions.")
      setIsFetchModalOpen(false)
    } catch (err) {
      alert("Error triggering fetch for some positions.")
    }
  }

  function handleSelectAllPositions(checked: boolean) {
    if (checked) {
      setSelectedPositionsForFetch(new Set(positions.map(p => p.id)))
    } else {
      setSelectedPositionsForFetch(new Set())
    }
  }

  function handleSelectPosition(id: string, checked: boolean) {
    const newSet = new Set(selectedPositionsForFetch)
    if (checked) newSet.add(id)
    else newSet.delete(id)
    setSelectedPositionsForFetch(newSet)
  }

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
    <div className="animate-fade-in w-full max-w-[1400px] mx-auto min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-zinc-100">Candidates</h1>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />
        </div>
        <span className="text-sm text-zinc-500">{filtered.length} candidate{filtered.length !== 1 ? 's' : ''}</span>
      </div>

      {processingCount > 0 && (
        <div className="mb-4 rounded-lg bg-blue-50 border border-blue-200 px-4 py-2 text-sm text-blue-700">
          {processingCount} CV{processingCount !== 1 ? 's' : ''} processing in background…
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
      <div className="glass-panel rounded-xl p-4 flex gap-3 mb-5 animate-slide-up animate-stagger-1">
        <input
          type="text"
          placeholder="Search by name or email…"
          value={nameSearch}
          onChange={(e) => setNameSearch(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 w-56 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-colors"
        />
        <select
          value={jobFilter}
          onChange={(e) => setJobFilter(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-indigo-500 w-48 truncate transition-colors"
        >
          <option value="">All positions</option>
          {Array.from(
            new Map(
              positions
                .filter((p) => p.title && p.title.trim() !== '' && p.title !== 'None' && p.title !== 'Unknown Title')
                .map((p) => [p.title!.trim(), p])
            ).values()
          ).map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-indigo-500 w-40 transition-colors"
        >
          <option value="">All sources</option>
          {sources.map((src) => (
            <option key={src.name} value={src.name}>
              {src.name.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
        <button
          onClick={handleFetchClick}
          className="inline-flex items-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-indigo-900/50 hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all"
        >
          Fetch Candidates
        </button>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="inline-flex items-center gap-2 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-4 py-2 text-sm font-medium text-indigo-400 shadow-sm hover:bg-indigo-500/20 disabled:opacity-60 disabled:cursor-not-allowed transition-all"
        >
          {uploading ? 'Uploading…' : 'Upload CV'}
        </button>
      </div>

      {isLoading && <p className="text-zinc-500 text-sm glass-panel p-4 rounded-xl animate-slide-up animate-stagger-2">Loading candidates…</p>}
      {isError && <p className="text-red-400 text-sm glass-panel p-4 rounded-xl">Failed to load candidates.</p>}
      {!isLoading && !isError && filtered.length === 0 && (
        <p className="text-zinc-500 text-sm glass-panel p-8 text-center rounded-xl animate-slide-up animate-stagger-2">No candidates match your filters.</p>
      )}

      {filtered.length > 0 && (
        <div className="w-full min-w-0 overflow-x-auto rounded-xl glass-panel animate-slide-up animate-stagger-2">
          <table className="w-full min-w-[960px] divide-y divide-zinc-800">
            <thead className="bg-zinc-900">
              <tr>
                {['Name', 'Email', 'Current Title', 'Location', 'Source', 'Experience', 'Status', ''].map((h) => (
                  <th
                    key={h || 'actions'}
                    className={`px-4 py-4 text-left text-xs font-semibold uppercase tracking-wider text-zinc-400 whitespace-nowrap${
                      h === '' ? ' sticky right-0 bg-zinc-900 z-10 text-right' : ''
                    }`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800 bg-zinc-950/30">
              {filtered.map((c) => (
                <tr
                  key={c.email}
                  onClick={() => navigate(`/candidates/${encodeURIComponent(c.email)}`)}
                  className="group cursor-pointer hover:bg-zinc-800/80 transition-colors"
                >
                  <td className="px-4 py-4 text-sm font-medium text-zinc-100 whitespace-nowrap group-hover:text-indigo-400 transition-colors">
                    {c.name ?? <span className="italic text-zinc-500">Processing…</span>}
                  </td>
                  <td className="px-4 py-4 text-sm text-zinc-400 whitespace-nowrap">
                    {c.email}
                  </td>
                  <td className="px-4 py-4 text-sm text-zinc-400 whitespace-nowrap">
                    {c.current_title ?? '—'}
                  </td>
                  <td className="px-4 py-4 text-sm text-zinc-400 whitespace-nowrap">
                    {c.location ?? '—'}
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap">
                    <SourceBadge source={c.source_name} />
                  </td>
                  <td className="px-4 py-4 text-sm text-zinc-400 whitespace-nowrap">
                    {c.years_experience != null ? `${c.years_experience} yrs` : '—'}
                  </td>
                  <td className="px-4 py-4 text-xs text-zinc-500 font-medium uppercase whitespace-nowrap">
                    {c.status}
                  </td>
                  <td className="sticky right-0 z-10 bg-zinc-900 px-4 py-4 text-right whitespace-nowrap group-hover:bg-zinc-800/80 transition-colors">
                    <button
                      onClick={(e) => handleDelete(e, c.email, c.name)}
                      disabled={deleteCandidate.isPending}
                      className="rounded-md border border-red-500/20 bg-red-500/10 px-2.5 py-1.5 text-xs font-semibold text-red-400 hover:bg-red-500/20 disabled:opacity-50 transition-colors"
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

      {isFetchModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-md rounded-2xl glass-panel p-6 shadow-2xl animate-slide-up border-zinc-700">
            <div className="flex items-center gap-4 mb-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 shadow-inner">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
                </svg>
              </div>
              <div>
                <h2 className="text-xl font-semibold text-zinc-100">Fetch Candidates</h2>
                <p className="text-sm text-zinc-400">Select job positions to sync new candidates.</p>
              </div>
            </div>
            
            <div className="max-h-60 overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-950/50 p-2 mb-6 shadow-inner space-y-1">
              <label className="flex items-center gap-3 p-3 hover:bg-zinc-800/80 rounded-lg cursor-pointer border border-transparent hover:border-zinc-700 transition-all shadow-sm mb-2 group">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-indigo-500 focus:ring-indigo-500 focus:ring-offset-zinc-900"
                  checked={positions.length > 0 && selectedPositionsForFetch.size === positions.length}
                  onChange={(e) => handleSelectAllPositions(e.target.checked)}
                />
                <span className="text-sm font-medium text-zinc-200 group-hover:text-white transition-colors">Select All Positions</span>
              </label>
              
              {positions.map((p) => (
                <label key={p.id} className="flex items-center gap-3 p-3 hover:bg-zinc-800/50 rounded-lg cursor-pointer border border-transparent hover:border-zinc-700 hover:shadow-sm transition-all group">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-indigo-500 focus:ring-indigo-500 focus:ring-offset-zinc-900"
                    checked={selectedPositionsForFetch.has(p.id)}
                    onChange={(e) => handleSelectPosition(p.id, e.target.checked)}
                  />
                  <span className="text-sm text-zinc-400 group-hover:text-zinc-200 transition-colors">{p.title}</span>
                </label>
              ))}
              {positions.length === 0 && (
                <p className="text-sm text-zinc-500 p-4 text-center">No positions available.</p>
              )}
            </div>

            <div className="flex justify-end gap-3 mt-4">
              <button
                onClick={() => setIsFetchModalOpen(false)}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 border border-zinc-700 bg-transparent transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleFetchSubmit}
                disabled={selectedPositionsForFetch.size === 0 || fetchCandidates.isPending}
                className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white shadow-lg hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {fetchCandidates.isPending && (
                  <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                )}
                {fetchCandidates.isPending ? 'Fetching...' : 'Start Fetch'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
