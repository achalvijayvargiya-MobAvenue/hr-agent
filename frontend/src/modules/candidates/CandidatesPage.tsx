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
import { Select } from '../../components/ui/Select'
import { useSyncStatus } from '../matches/hooks/useMatches'

const SOURCE_STYLES: Record<string, string> = {
  local_kb: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
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

function ApplicationStatusBadge({ status }: { status: string | null | undefined }) {
  if (!status) return null

  // Based on actual Zoho Recruit statuses
  let bgClass = 'bg-zinc-800/50 text-zinc-400 border-zinc-700/50'
  const lower = status.toLowerCase()

  if (lower.includes('reject')) {
    bgClass = 'bg-red-500/10 text-red-400 border-red-500/20'
  } else if (lower.includes('interview')) {
    bgClass = 'bg-blue-500/10 text-blue-400 border-blue-500/20'
  } else if (lower.includes('hired')) {
    bgClass = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
  } else if (lower.includes('associated') || lower.includes('applied')) {
    bgClass = 'bg-sky-500/10 text-sky-400 border-sky-500/20'
  }

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border ${bgClass} whitespace-nowrap`}>
      {status}
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
          className="rounded-lg bg-orange-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-orange-500 disabled:opacity-60 transition-colors"
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
  const [applicantsOnly, setApplicantsOnly] = useState(false)

  const { data: candidates = [], isLoading, isError } = useCandidates(
    sourceFilter || undefined,
    jobFilter || undefined,
    applicantsOnly
  )
  const { data: conflicts = [] } = useCandidateConflicts()
  const { data: imports = [] } = useCandidateImports()
  const deleteCandidate = useDeleteCandidate()
  const resolveConflict = useResolveConflict()
  const dismissImport = useDismissImport()
  const syncStatus = useSyncStatus()

  const processingCount = imports.filter((i) => i.status === 'PROCESSING').length
  const failedImports = imports.filter((i) => i.status === 'FAILED')

  const fetchCandidates = useFetchCandidates()
  const [isFetchModalOpen, setIsFetchModalOpen] = useState(false)
  const [selectedPositionsForFetch, setSelectedPositionsForFetch] = useState<Set<string>>(new Set())
  const [fetchMessage, setFetchMessage] = useState<string | null>(null)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [candidateToDelete, setCandidateToDelete] = useState<{email: string, name: string | null} | null>(null)
  const [syncNotification, setSyncNotification] = useState<{ title: string; message: string; type: 'info' | 'success' } | null>(null)

  function handleFetchClick() {
    setFetchError(null)
    setFetchMessage(null)
    setIsFetchModalOpen(true)
  }

  async function handleFetchSubmit() {
    setFetchError(null)
    setFetchMessage(null)
    if (selectedPositionsForFetch.size === 0) {
      setFetchError("Please select at least one position.")
      return
    }
    const promises = Array.from(selectedPositionsForFetch).map(id => fetchCandidates.mutateAsync(id))
    try {
      const results = await Promise.all(promises)
      setIsFetchModalOpen(false)
      
      const totalNewCandidates = results.reduce((acc, res) => acc + (res.new_candidates || 0), 0)
      
      if (totalNewCandidates === 0) {
        setSyncNotification({
          title: 'Up to Date',
          message: 'No new candidates were fetched from the sources.',
          type: 'info'
        })
      } else {
        setSyncNotification({
          title: 'Sync Successful',
          message: `Successfully fetched and queued ${totalNewCandidates} new candidate(s) for processing.`,
          type: 'success'
        })
      }
    } catch (err) {
      setFetchError("Error triggering fetch for some positions.")
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
    setCandidateToDelete({ email, name: candidateName })
  }

  function confirmDelete() {
    if (candidateToDelete) {
      deleteCandidate.mutate(candidateToDelete.email)
      setCandidateToDelete(null)
    }
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
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-zinc-100">Candidates</h1>
          <span className="inline-flex items-center rounded-md bg-zinc-800 px-2 py-1 text-xs font-medium text-zinc-300 border border-zinc-700">
            {filtered.length} candidate{filtered.length !== 1 ? 's' : ''}
          </span>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 rounded-lg border border-orange-500/30 bg-orange-500/10 px-4 py-2 text-sm font-medium text-orange-400 hover:bg-orange-500/20 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m3.75 9v6m3-3H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
            {uploading ? 'Uploading…' : 'Upload CV'}
          </button>
          
          {jobFilter && (
            <button
              onClick={() => syncStatus.mutate(jobFilter)}
              disabled={syncStatus.isPending}
              className="flex items-center gap-2 rounded-lg border border-orange-500/30 bg-orange-500/10 px-4 py-2 text-sm font-medium text-orange-400 hover:bg-orange-500/20 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {syncStatus.isPending ? (
                <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
                </svg>
              )}
              {syncStatus.isPending ? 'Syncing...' : 'Sync Status'}
            </button>
          )}

          <button
            onClick={handleFetchClick}
            className="flex items-center gap-2 rounded-lg bg-orange-600 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-orange-900/50 hover:bg-orange-500 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
            Fetch Candidates
          </button>
        </div>
      </div>

      {processingCount > 0 && (
        <div className="mb-6 rounded-xl border border-orange-500/20 bg-orange-500/5 p-4 flex items-center gap-4 animate-pulse">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 animate-spin text-orange-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-orange-400">Processing Candidates</h3>
            <p className="text-xs text-orange-400/80 mt-0.5">
              {processingCount} candidate{processingCount !== 1 ? 's are' : ' is'} being processed in the background. They will appear here once ready.
            </p>
          </div>
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
          <h2 className="text-sm font-semibold text-orange-900 uppercase tracking-wide">
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
      <div className="glass-panel rounded-xl p-4 flex flex-wrap gap-4 mb-5 animate-slide-up animate-stagger-1 items-center relative z-40">
        <div className="relative flex-1 min-w-[240px] max-w-md">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
            <svg className="h-5 w-5 text-zinc-500" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clipRule="evenodd" />
            </svg>
          </div>
          <input
            type="text"
            placeholder="Search by name or email…"
            value={nameSearch}
            onChange={(e) => setNameSearch(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950/50 pl-10 pr-4 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-orange-500 transition-colors"
          />
        </div>
        <Select
          value={jobFilter}
          onChange={setJobFilter}
          options={[
            { label: 'All positions', value: '' },
            ...Array.from(
              new Map(
                positions
                  .filter((p) => p.title && p.title.trim() !== '' && p.title !== 'None' && p.title !== 'Unknown Title')
                  .map((p) => [p.title!.trim(), p])
              ).values()
            ).map((p) => ({ label: p.title as string, value: p.id }))
          ]}
          className="w-48 rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2.5 transition-colors"
        />
        {jobFilter && (
          <Select
            value={applicantsOnly ? 'true' : 'false'}
            onChange={(val) => setApplicantsOnly(val === 'true')}
            options={[
              { label: 'Include AI Pool', value: 'false' },
              { label: 'Applicants Only', value: 'true' }
            ]}
            className="w-48 rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2.5 transition-colors"
          />
        )}
        <Select
          value={sourceFilter}
          onChange={setSourceFilter}
          options={[
            { label: 'All sources', value: '' },
            ...sources.map((src) => ({ label: src.name.replace(/_/g, ' '), value: src.name }))
          ]}
          className="w-40 rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2.5 transition-colors"
        />
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
                {['Name', 'Email', 'Current Title', 'Location', 'Application Status', 'Source', 'Experience', 'Status', ''].map((h) => (
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
                  <td className="px-4 py-4 text-sm font-medium text-zinc-100 whitespace-nowrap group-hover:text-orange-400 transition-colors">
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
                    <div className="flex flex-wrap gap-1">
                      {jobFilter 
                        ? (c.application_statuses?.[jobFilter] 
                            ? <ApplicationStatusBadge status={c.application_statuses[jobFilter]} /> 
                            : '—')
                        : Object.values(c.application_statuses || {}).length > 0 
                          ? Object.values(c.application_statuses).map((st, i) => (
                              <ApplicationStatusBadge key={i} status={st} />
                            ))
                          : '—'
                      }
                    </div>
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
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-400 shadow-inner">
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
                  className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-orange-500 focus:ring-orange-500 focus:ring-offset-zinc-900"
                  checked={positions.length > 0 && selectedPositionsForFetch.size === positions.length}
                  onChange={(e) => handleSelectAllPositions(e.target.checked)}
                />
                <span className="text-sm font-medium text-zinc-200 group-hover:text-white transition-colors">Select All Positions</span>
              </label>
              
              {positions.map((p) => (
                <label key={p.id} className="flex items-center gap-3 p-3 hover:bg-zinc-800/50 rounded-lg cursor-pointer border border-transparent hover:border-zinc-700 hover:shadow-sm transition-all group">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-orange-500 focus:ring-orange-500 focus:ring-offset-zinc-900"
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

            {fetchError && (
              <p className="text-sm text-red-400 mb-3 px-1">{fetchError}</p>
            )}
            {fetchMessage && (
              <p className="text-sm text-green-400 mb-3 px-1">{fetchMessage}</p>
            )}

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
                className="flex items-center gap-2 rounded-lg bg-orange-600 px-5 py-2.5 text-sm font-medium text-white shadow-lg hover:bg-orange-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
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

      {candidateToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-md rounded-2xl glass-panel p-6 shadow-2xl animate-slide-up border-zinc-700">
            <div className="flex items-center gap-4 mb-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-500/10 border border-red-500/20 text-red-400 shadow-inner">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div>
                <h2 className="text-xl font-semibold text-zinc-100">Delete Candidate</h2>
                <p className="text-sm text-zinc-400">This action cannot be undone.</p>
              </div>
            </div>
            
            <p className="text-zinc-300 text-sm mb-8 px-1">
              Are you sure you want to permanently delete <span className="font-semibold text-zinc-100">{candidateToDelete.name ?? candidateToDelete.email}</span>?
            </p>

            <div className="flex justify-end gap-3 mt-4">
              <button
                onClick={() => setCandidateToDelete(null)}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 border border-zinc-700 bg-transparent transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleteCandidate.isPending}
                className="flex items-center gap-2 rounded-lg bg-red-600 px-5 py-2.5 text-sm font-medium text-white shadow-lg hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {deleteCandidate.isPending ? 'Deleting...' : 'Delete Permanently'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sync Notification Modal */}
      {syncNotification && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md rounded-2xl glass-panel p-6 shadow-2xl animate-slide-up border-zinc-700">
            <div className="flex items-center gap-3 mb-2">
              {syncNotification.type === 'success' ? (
                <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              ) : (
                <svg className="w-6 h-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
              <h2 className="text-lg font-semibold text-zinc-100">
                {syncNotification.title}
              </h2>
            </div>
            <p className="text-sm text-zinc-300 mb-6">
              {syncNotification.message}
            </p>
            <div className="flex justify-end">
              <button
                onClick={() => setSyncNotification(null)}
                className="rounded-lg bg-orange-600 px-4 py-2 text-sm font-semibold text-white hover:bg-orange-500 shadow-lg transition-colors focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 focus:ring-offset-zinc-900"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
