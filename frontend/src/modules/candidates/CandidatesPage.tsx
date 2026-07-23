import { useRef, useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Upload, Search, Loader2, Trash2, CloudDownload, Users as UsersIcon, ShieldAlert, RefreshCw, Cpu } from 'lucide-react'
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
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../../components/ui/Table'
import { Modal } from '../../components/ui/Modal'

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
        <div className="flex items-center gap-2 mb-1">
          <ShieldAlert size={16} className="text-yellow-500" />
          <p className="text-sm font-semibold text-yellow-500">
            Duplicate email: {conflict.proposed_email}
          </p>
        </div>
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
  const [applicantsOnly, setApplicantsOnly] = useState(false)
  const [page, setPage] = useState(1)
  const limit = 50

  const { data: paginatedData, isLoading, isError } = useCandidates(
    sourceFilter || undefined,
    jobFilter || undefined,
    applicantsOnly,
    undefined,
    page,
    limit
  )
  const candidates = paginatedData?.items || []
  const totalItems = paginatedData?.total || 0
  const totalPages = Math.ceil(totalItems / limit)
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
  const [candidateToDelete, setCandidateToDelete] = useState<{ email: string, name: string | null } | null>(null)
  const [selectedEmails, setSelectedEmails] = useState<Set<string>>(new Set())
  const [bulkDeleting, setBulkDeleting] = useState(false)
  const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false)
  const [syncNotification, setSyncNotification] = useState<{ title: string; message: string; type: 'info' | 'success' } | null>(null)

  const FETCH_LOADING_TEXTS = [
    "Connecting to integration sources...",
    "Searching for new applications...",
    "Downloading candidate resumes...",
    "AI is analyzing skillset & experience...",
    "Extracting structured data...",
    "Comparing against job requirements...",
    "Finalizing candidate profiles..."
  ]
  const [loadingTextIdx, setLoadingTextIdx] = useState(0)

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;
    if (fetchCandidates.isPending) {
      interval = setInterval(() => {
        setLoadingTextIdx(prev => (prev + 1) % FETCH_LOADING_TEXTS.length)
      }, 2500)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [fetchCandidates.isPending, FETCH_LOADING_TEXTS.length])

  function handleFetchClick() {
    setIsFetchModalOpen(true)
  }

  async function handleFetchSubmit() {
    if (selectedPositionsForFetch.size === 0) {
      toast.error("Please select at least one position.")
      return
    }

    try {
      const promises = Array.from(selectedPositionsForFetch).map(id => fetchCandidates.mutateAsync(id))
      const results = await Promise.all(promises)
      setIsFetchModalOpen(false)
      const totalNewCandidates = results.reduce((acc, res) => acc + (res.new_candidates || 0), 0)

      if (totalNewCandidates === 0) {
        setSyncNotification({
          title: 'Up to Date',
          message: 'Everything is up to date! No new candidates were found across your integrated platforms.',
          type: 'info'
        })
      } else {
        setSyncNotification({
          title: 'Sync Successful',
          message: `Awesome! We successfully fetched ${totalNewCandidates} new candidate(s).\nThey are now queued for AI processing.`,
          type: 'success'
        })
      }
    } catch (error) {
      toast.error("Error triggering fetch for some positions.")
      console.error(error)
      setIsFetchModalOpen(false)
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
      toast.success("Candidate deleted successfully.")
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

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    if (files.length === 0) return
    e.target.value = ''
    setUploading(true)

    const promise = new Promise((resolve, reject) => {
      Promise.allSettled(
        files.map(async (file) => {
          const form = new FormData()
          form.append('file', file)
          await api.post('/candidates/upload', form, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
        })
      ).then(results => {
        const succeeded = results.filter((r) => r.status === 'fulfilled').length
        const failed = results.length - succeeded

        if (succeeded > 0) {
          queryClient.invalidateQueries({ queryKey: ['candidates'] })
          queryClient.invalidateQueries({ queryKey: ['candidate-imports'] })
          queryClient.invalidateQueries({ queryKey: ['candidate-conflicts'] })
        }

        if (failed > 0) {
          const firstFailure = results.find((r) => r.status === 'rejected') as PromiseRejectedResult | undefined
          const detail = (firstFailure?.reason as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Upload failed.'
          reject(new Error(failed === files.length ? detail : `${failed} of ${files.length} uploads failed. ${detail}`))
        } else {
          resolve(succeeded === 1 ? 'CV uploaded — processing in background' : `${succeeded} CVs uploaded — processing in background`)
        }
      })
    })

    toast.promise(promise, {
      loading: 'Uploading CVs...',
      success: (msg) => `${msg}`,
      error: (err) => err.message,
    })

    setUploading(false)
  }

  const handleBulkDelete = async () => {
    setBulkDeleting(true)
    try {
      await Promise.all(
        Array.from(selectedEmails).map(email =>
          api.delete(`/candidates/${encodeURIComponent(email)}`)
        )
      )
      toast.success(`${selectedEmails.size} candidates deleted successfully.`)
      setSelectedEmails(new Set())
      queryClient.invalidateQueries({ queryKey: ['candidates'] })
      setBulkDeleteModalOpen(false)
    } catch {
      toast.error('Failed to delete some candidates.')
    } finally {
      setBulkDeleting(false)
    }
  }

  const handleExportCSV = () => {
    const selectedCandidates = candidates.filter(c => selectedEmails.has(c.email))
    if (selectedCandidates.length === 0) return

    const headers = ['Name', 'Email', 'Current Title', 'Location', 'Experience (Years)', 'Source']
    const csvContent = [
      headers.join(','),
      ...selectedCandidates.map(c =>
        [
          `"${c.name || ''}"`,
          `"${c.email}"`,
          `"${c.current_title || ''}"`,
          `"${c.location || ''}"`,
          c.years_experience ?? '',
          `"${c.source_name || ''}"`
        ].join(',')
      )
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.setAttribute('href', url)
    link.setAttribute('download', `candidates_export_${new Date().toISOString().split('T')[0]}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // Backend handles search and pagination
  const hasActiveFilters = !!(sourceFilter || jobFilter || applicantsOnly)

  return (
    <div className="animate-fade-in w-full max-w-[1400px] mx-auto min-w-0 pb-12">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-white">Candidates</h1>
          <span className="inline-flex items-center rounded-md bg-zinc-800 px-2 py-1 text-xs font-medium text-zinc-300 border border-zinc-700 shadow-sm">
            {totalItems} candidate{totalItems !== 1 ? 's' : ''}
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
          {jobFilter && (
            <button
              onClick={() => {
                const promise = new Promise((resolve, reject) => {
                  syncStatus.mutate(jobFilter, {
                    onSuccess: () => resolve('Successfully synced statuses.'),
                    onError: () => reject(new Error('Failed to sync statuses.'))
                  })
                })
                toast.promise(promise, {
                  loading: 'Syncing statuses...',
                  success: (msg) => `${msg}`,
                  error: (err) => err.message,
                })
              }}
              disabled={syncStatus.isPending}
              className="flex items-center gap-2 rounded-lg border border-orange-500/30 bg-orange-500/10 px-4 py-2 text-sm font-medium text-orange-400 hover:bg-orange-500/20 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {syncStatus.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Sync Status
            </button>
          )}

          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 rounded-lg border border-orange-500/30 bg-orange-500/10 px-4 py-2 text-sm font-medium text-orange-400 hover:bg-orange-500/20 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            Upload CV
          </button>

          <button
            onClick={handleFetchClick}
            className="flex items-center gap-2 rounded-lg bg-orange-600 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-orange-900/50 hover:bg-orange-500 transition-colors"
          >
            <CloudDownload size={16} />
            Fetch Candidates
          </button>
        </div>
      </div>

      {processingCount > 0 && (
        <div className="mb-6 rounded-xl border border-orange-500/20 bg-orange-500/5 p-4 flex items-center gap-4 animate-pulse">
          <div className="flex-shrink-0">
            <Loader2 size={20} className="animate-spin text-orange-400" />
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

      {/* Filters */}
      <div className="flex items-center gap-3 mb-5 animate-slide-up animate-stagger-1 relative z-40">
        <span className="text-sm font-medium text-zinc-400">Filter by:</span>
        <Select
          value={jobFilter}
          onChange={(val) => { setJobFilter(val); setPage(1); }}
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
          className="w-56 rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2.5 transition-colors"
        />
        {jobFilter && (
          <Select
            value={applicantsOnly ? 'true' : 'false'}
            onChange={(val) => { setApplicantsOnly(val === 'true'); setPage(1); }}
            options={[
              { label: 'Include AI Pool', value: 'false' },
              { label: 'Applicants Only', value: 'true' }
            ]}
            className="w-48 rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2.5 transition-colors"
          />
        )}
        <Select
          value={sourceFilter}
          onChange={(val) => { setSourceFilter(val); setPage(1); }}
          options={[
            { label: 'All sources', value: '' },
            ...sources.map((src) => ({ label: src.name.replace(/_/g, ' '), value: src.name }))
          ]}
          className="w-40 rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2.5 transition-colors"
        />
      </div>

      {isLoading && (
        <div className="flex items-center gap-3 py-12 justify-center text-zinc-500 bg-zinc-900/30 rounded-xl border border-zinc-800 animate-slide-up animate-stagger-2">
          <Loader2 size={24} className="animate-spin text-orange-500" />
          <span className="text-sm font-medium">Loading candidates…</span>
        </div>
      )}
      {isError && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-sm animate-slide-up">
          Failed to load candidates. Please try again.
        </div>
      )}
      {!isLoading && !isError && candidates.length === 0 && hasActiveFilters && (
        <div className="py-20 px-6 text-center bg-zinc-900/30 rounded-xl border border-zinc-800 animate-slide-up animate-stagger-2">
          <div className="relative mx-auto w-24 h-24 mb-6">
            <div className="absolute inset-0 bg-orange-500/20 blur-xl rounded-full animate-pulse"></div>
            <div className="relative bg-zinc-900 border border-zinc-800 rounded-full w-full h-full flex items-center justify-center shadow-lg">
              <Search size={40} className="text-zinc-600" />
            </div>
            <div className="absolute -bottom-2 -right-2 bg-orange-500 text-white rounded-full p-2 border-4 border-zinc-950 shadow-sm">
              <UsersIcon size={16} />
            </div>
          </div>
          <h3 className="text-xl font-semibold text-zinc-100">No candidates match your filters</h3>
          <p className="text-zinc-400 mt-2 text-sm max-w-sm mx-auto mb-6">
            We couldn't find anyone matching the current criteria. Try adjusting your filters or clearing them to see more candidates.
          </p>
          <button
            onClick={() => {
              setSourceFilter('')
              setJobFilter('')
              setApplicantsOnly(false)
            }}
            className="inline-flex items-center gap-2 rounded-lg bg-orange-600/10 px-5 py-2.5 text-sm font-semibold text-orange-400 hover:bg-orange-600/20 transition-colors border border-orange-500/20 shadow-sm"
          >
            <RefreshCw size={16} />
            Clear All Filters
          </button>
        </div>
      )}

      {!isLoading && !isError && candidates.length === 0 && !hasActiveFilters && (
        <div className="py-16 px-6 text-center bg-zinc-900/30 rounded-xl border border-zinc-800 animate-slide-up animate-stagger-2">
          <UsersIcon size={48} className="text-zinc-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-zinc-300">No candidates found</h3>
          <p className="text-zinc-500 mt-2 text-sm max-w-sm mx-auto">Upload candidate CVs or fetch from connected sources.</p>
        </div>
      )}

      {candidates.length > 0 && (
        <div className="animate-slide-up animate-stagger-2">
          <Table>
            <TableHeader>
              <tr>
                <TableHead className="w-12 text-center">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-orange-500 focus:ring-orange-500 focus:ring-offset-zinc-900 cursor-pointer"
                    checked={candidates.length > 0 && selectedEmails.size === candidates.length}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedEmails(new Set(candidates.map(c => c.email)))
                      } else {
                        setSelectedEmails(new Set())
                      }
                    }}
                  />
                </TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Current Title</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Application Status</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Experience</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right"></TableHead>
              </tr>
            </TableHeader>
            <TableBody>
              {candidates.map((c) => (
                <TableRow
                  key={c.email}
                  onClick={() => navigate(`/candidates/${encodeURIComponent(c.email)}`)}
                  className="cursor-pointer group hover:bg-zinc-800/40 transition-colors"
                >
                  <TableCell className="w-12 text-center" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-orange-500 focus:ring-orange-500 focus:ring-offset-zinc-900 cursor-pointer"
                      checked={selectedEmails.has(c.email)}
                      onChange={(e) => {
                        const newSet = new Set(selectedEmails)
                        if (e.target.checked) {
                          newSet.add(c.email)
                        } else {
                          newSet.delete(c.email)
                        }
                        setSelectedEmails(newSet)
                      }}
                    />
                  </TableCell>
                  <TableCell className="font-medium text-zinc-100 group-hover:text-orange-400">
                    {c.name ?? <span className="italic text-zinc-500">Processing…</span>}
                  </TableCell>
                  <TableCell className="text-zinc-400">{c.email}</TableCell>
                  <TableCell className="text-zinc-400">{c.current_title ?? '—'}</TableCell>
                  <TableCell className="text-zinc-400">{c.location ?? '—'}</TableCell>
                  <TableCell>
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
                  </TableCell>
                  <TableCell>
                    <SourceBadge source={c.source_name} />
                  </TableCell>
                  <TableCell className="text-zinc-400">
                    {c.years_experience != null ? `${c.years_experience} yrs` : '—'}
                  </TableCell>
                  <TableCell className="text-xs text-zinc-500 font-medium uppercase">
                    {c.status}
                  </TableCell>
                  <TableCell className="text-right">
                    <button
                      onClick={(e) => handleDelete(e, c.email, c.name)}
                      disabled={deleteCandidate.isPending}
                      className="inline-flex items-center justify-center p-1.5 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 rounded-md transition-colors disabled:opacity-50"
                    >
                      <Trash2 size={16} />
                    </button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6 px-4 py-3 bg-zinc-900/50 border border-zinc-800 rounded-xl animate-slide-up">
          <div className="text-sm text-zinc-400">
            Showing <span className="font-medium text-zinc-200">{(page - 1) * limit + 1}</span> to{' '}
            <span className="font-medium text-zinc-200">{Math.min(page * limit, totalItems)}</span> of{' '}
            <span className="font-medium text-zinc-200">{totalItems}</span> results
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 text-sm font-medium rounded-md border border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700 disabled:opacity-50 transition-colors"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1.5 text-sm font-medium rounded-md border border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700 disabled:opacity-50 transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}

      <Modal
        isOpen={isFetchModalOpen}
        onClose={() => {
          if (!fetchCandidates.isPending) setIsFetchModalOpen(false)
        }}
        title={fetchCandidates.isPending ? "Syncing Candidates..." : "Fetch Candidates"}
        size="md"
      >
        {fetchCandidates.isPending ? (
          <div className="flex flex-col items-center justify-center py-10 px-4 space-y-6">
            <div className="relative flex items-center justify-center mb-4">
              <div className="absolute inset-0 bg-orange-500/20 blur-xl rounded-full animate-pulse"></div>
              <div className="relative bg-orange-500/10 text-orange-400 p-5 rounded-full border border-orange-500/30 shadow-[0_0_20px_rgba(249,115,22,0.15)]">
                <Cpu size={48} className="animate-bounce" style={{ animationDuration: '2s' }} />
              </div>
            </div>

            <div className="flex flex-col items-center space-y-3 text-center min-h-[80px]">
              <h3 className="text-lg font-semibold text-white">AI Processing in Progress</h3>
              <p className="text-orange-400 font-medium transition-opacity duration-300 animate-pulse">
                {FETCH_LOADING_TEXTS[loadingTextIdx]}
              </p>
            </div>
            <p className="text-xs text-zinc-500 mt-4 max-w-[250px] text-center">
              Please do not close this window. This may take a moment depending on candidate volume.
            </p>
          </div>
        ) : (
          <>
            <p className="text-sm text-zinc-400 mb-6">Select job positions to sync new candidates from connected integrations.</p>

            <div className="max-h-80 overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-950/50 p-2 mb-6 shadow-inner space-y-1 custom-scrollbar">
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

            <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-zinc-800">
              <button
                onClick={() => setIsFetchModalOpen(false)}
                className="px-4 py-2 text-sm font-medium text-zinc-300 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleFetchSubmit}
                disabled={fetchCandidates.isPending || selectedPositionsForFetch.size === 0}
                className="px-4 py-2 text-sm font-medium bg-orange-600 hover:bg-orange-500 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {fetchCandidates.isPending && <Loader2 size={16} className="animate-spin" />}
                Start Fetch
              </button>
            </div>
          </>
        )}
      </Modal>

      {/* Sync Notification Modal */}
      <Modal
        isOpen={!!syncNotification}
        onClose={() => setSyncNotification(null)}
        title={syncNotification?.title || 'Notification'}
        size="md"
      >
        <div className="flex flex-col items-center justify-center w-full">
          {syncNotification?.type === 'success' ? (
            <div className="w-12 h-12 bg-orange-500/10 text-orange-400 rounded-full flex items-center justify-center mb-4 shadow-[0_0_15px_rgba(249,115,22,0.1)]">
              <CloudDownload size={24} />
            </div>
          ) : (
            <div className="w-12 h-12 bg-zinc-800 text-zinc-400 rounded-full flex items-center justify-center mb-4">
              <RefreshCw size={24} />
            </div>
          )}
          <p className="text-zinc-300 text-base mb-6 max-w-sm text-center whitespace-pre-wrap">
            {syncNotification?.message}
          </p>
          <button
            onClick={() => setSyncNotification(null)}
            className="w-full bg-orange-600 hover:bg-orange-500 text-white font-medium py-2 rounded-lg transition-all duration-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 focus:ring-offset-zinc-900"
          >
            Done
          </button>
        </div>
      </Modal>

      {candidateToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/80 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-md rounded-2xl bg-zinc-900 border border-zinc-800 p-6 shadow-2xl animate-slide-up">
            <h2 className="text-lg font-semibold text-zinc-100 mb-2">Delete Candidate</h2>
            <p className="text-zinc-400 text-sm mb-6">
              Are you sure you want to permanently delete <span className="font-semibold text-zinc-100">{candidateToDelete.name ?? candidateToDelete.email}</span>? This action cannot be undone.
            </p>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setCandidateToDelete(null)}
                className="rounded-lg px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleteCandidate.isPending}
                className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-50 transition-colors"
              >
                {deleteCandidate.isPending && <Loader2 size={14} className="animate-spin" />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Bulk Action Bar */}
      {selectedEmails.size > 0 && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-40 animate-slide-up">
          <div className="flex items-center gap-4 bg-zinc-900 border border-zinc-700 shadow-2xl rounded-full px-6 py-3">
            <span className="text-sm font-medium text-white bg-orange-600 px-2.5 py-0.5 rounded-full shadow-sm">
              {selectedEmails.size} selected
            </span>

            <div className="w-px h-6 bg-zinc-700"></div>

            <button
              onClick={handleExportCSV}
              className="text-sm font-medium text-zinc-300 hover:text-white flex items-center gap-2 transition-colors group"
            >
              <CloudDownload size={16} className="text-zinc-500 group-hover:text-white transition-colors" />
              Export CSV
            </button>

            <div className="w-px h-6 bg-zinc-700"></div>

            <button
              onClick={() => setBulkDeleteModalOpen(true)}
              className="text-sm font-medium text-red-400 hover:text-red-300 flex items-center gap-2 transition-colors group"
            >
              <Trash2 size={16} className="text-red-500/70 group-hover:text-red-400 transition-colors" />
              Delete Selected
            </button>

            <div className="w-px h-6 bg-zinc-700"></div>

            <button
              onClick={() => setSelectedEmails(new Set())}
              className="text-sm font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Bulk Delete Modal */}
      {bulkDeleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/80 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-md rounded-2xl bg-zinc-900 border border-zinc-800 p-6 shadow-2xl animate-slide-up">
            <h2 className="text-lg font-semibold text-zinc-100 mb-2">Delete {selectedEmails.size} Candidates</h2>
            <p className="text-zinc-400 text-sm mb-6">
              Are you sure you want to permanently delete {selectedEmails.size} candidate{selectedEmails.size > 1 ? 's' : ''}? This action cannot be undone.
            </p>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setBulkDeleteModalOpen(false)}
                className="rounded-lg px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleBulkDelete}
                disabled={bulkDeleting}
                className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-50 transition-colors"
              >
                {bulkDeleting && <Loader2 size={14} className="animate-spin" />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
