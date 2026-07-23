import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, RefreshCw, Plus, Search, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { usePositions, useUploadPosition, useSyncZohoPositions } from './hooks/usePositions'
import ManualPositionForm from './ManualPositionForm'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../../components/ui/Table'
import { Drawer } from '../../components/ui/Drawer'
import { Modal } from '../../components/ui/Modal'


const STATUS_STYLES: Record<string, string> = {
  DRAFT: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  OPEN: 'bg-green-500/10 text-green-400 border-green-500/20',
  CLOSED: 'bg-zinc-800 text-zinc-400 border-zinc-700',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-semibold tracking-wider uppercase border ${STATUS_STYLES[status] ?? 'bg-zinc-800 text-zinc-400 border-zinc-700'}`}
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


  const [uploadOpen, setUploadOpen] = useState(false)
  const [slideOverOpen, setSlideOverOpen] = useState(false)
  const [syncNotification, setSyncNotification] = useState<{
    title: string;
    message: string;
    type: 'info' | 'success';
    added?: number;
    updated?: number;
    added_titles?: string[];
    updated_titles?: string[];
  } | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (f) {
      setSelectedFile(f)
    }
  }

  async function handleUpload() {
    if (!selectedFile) return
    const promise = new Promise((resolve, reject) => {
      upload.mutate(selectedFile, {
        onSuccess: (data) => {
          setSelectedFile(null)
          if (fileRef.current) fileRef.current.value = ''
          setUploadOpen(false)
          resolve(data.message)
        },
        onError: (err: unknown) => {
          const msg =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            'Upload failed.'
          reject(new Error(msg))
        },
      })
    })

    toast.promise(promise, {
      loading: 'Uploading job description...',
      success: (data) => `${data}`,
      error: (err) => err.message,
    })
  }

  const processingPositions = positions.filter(p => p.status === 'EXTRACTED' || p.status === 'STRUCTURED')
  const readyPositions = positions.filter(p => p.status !== 'EXTRACTED' && p.status !== 'STRUCTURED')

  return (
    <div className="animate-fade-in w-full max-w-[1400px] mx-auto min-w-0 pb-12">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-white">Positions</h1>
          <span className="inline-flex items-center rounded-md bg-zinc-800 px-2 py-1 text-xs font-medium text-zinc-300 border border-zinc-700 shadow-sm">
            {positions.length} position{positions.length !== 1 ? 's' : ''}
          </span>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => {
              syncZoho.mutate(undefined, {
                onSuccess: (data) => {
                  if (data.added === 0 && data.updated === 0) {
                    setSyncNotification({
                      title: 'Up to Date',
                      message: 'Everything is up to date! No new changes were found in Zoho.',
                      type: 'info'
                    })
                  } else {
                    let message = 'Zoho sync complete!\n';
                    if (data.added > 0 && data.updated > 0) {
                      message += `We just added ${data.added} brand new position(s) and updated ${data.updated} existing one(s).`;
                    } else if (data.added > 0) {
                      message += `We just added ${data.added} brand new position(s) to your workspace.`;
                    } else if (data.updated > 0) {
                      message += `We just updated ${data.updated} existing position(s) with the latest details.`;
                    }

                    setSyncNotification({
                      title: 'Sync Successful',
                      message,
                      type: 'success'
                    })
                  }
                },
                onError: () => toast.error('Failed to sync positions from Zoho.')
              })
            }}
            disabled={syncZoho.isPending}
            className="flex items-center gap-2 rounded-lg border border-orange-500/30 bg-orange-500/10 px-4 py-2 text-sm font-medium text-orange-400 hover:bg-orange-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {syncZoho.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            Fetch Positions
          </button>

          <button
            onClick={() => setUploadOpen(true)}
            className="flex items-center gap-2 rounded-lg border border-orange-500/30 bg-orange-500/10 px-4 py-2 text-sm font-medium text-orange-400 hover:bg-orange-500/20 transition-colors shadow-sm"
          >
            <Upload size={16} />
            Upload JD
          </button>
          <button
            onClick={() => setSlideOverOpen(true)}
            className="flex items-center gap-2 rounded-lg bg-orange-600 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-orange-900/50 hover:bg-orange-500 transition-colors"
          >
            <Plus size={16} />
            Create Manual
          </button>
        </div>
      </div>

      {/* Table */}
      {isLoading && (
        <div className="flex items-center gap-3 py-12 justify-center text-zinc-500 bg-zinc-900/30 rounded-xl border border-zinc-800 animate-slide-up animate-stagger-2">
          <Loader2 size={24} className="animate-spin text-orange-500" />
          <span className="text-sm font-medium">Loading positions…</span>
        </div>
      )}
      {isError && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-sm animate-slide-up">
          Failed to load positions. Please try again.
        </div>
      )}
      {!isLoading && !isError && positions.length === 0 && (
        <div className="py-16 px-6 text-center bg-zinc-900/30 rounded-xl border border-zinc-800 animate-slide-up animate-stagger-2">
          <BriefcaseIcon className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-zinc-300">No positions found</h3>
          <p className="text-zinc-500 mt-2 text-sm max-w-sm mx-auto">Get started by uploading a job description or creating a position manually.</p>
        </div>
      )}
      {positions.length > 0 && (
        <div className="animate-slide-up animate-stagger-2">
          <Table>
            <TableHeader>
              <tr>
                <TableHead>Title</TableHead>
                <TableHead>Department</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-center">Candidates Required</TableHead>
                <TableHead>Created</TableHead>
              </tr>
            </TableHeader>
            <TableBody>
              {processingPositions.length > 0 && (
                <TableRow hover={false} className="animate-pulse bg-orange-500/5">
                  <TableCell colSpan={5}>
                    <div className="flex items-center gap-3 py-1">
                      <Loader2 size={16} className="animate-spin text-orange-400" />
                      <span className="text-sm font-semibold text-orange-400">
                        {processingPositions.length === 1 ? 'Processing 1 job description...' : `Processing ${processingPositions.length} job descriptions...`}
                      </span>
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {readyPositions.map((p) => (
                <TableRow
                  key={p.id}
                  onClick={() => navigate(`/positions/${p.id}`)}
                >
                  <TableCell className="font-medium text-zinc-100 group-hover:text-orange-400">
                    {p.title ?? <span className="italic text-zinc-500">Processing…</span>}
                  </TableCell>
                  <TableCell className="text-zinc-400">{p.department ?? '—'}</TableCell>
                  <TableCell>
                    <StatusBadge status={p.position_status} />
                  </TableCell>
                  <TableCell className="text-center text-zinc-400">
                    {p.candidates_required ?? '—'}
                  </TableCell>
                  <TableCell className="text-zinc-500 text-xs">
                    {new Date(p.created_at).toLocaleDateString(undefined, {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric'
                    })}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Upload JD Modal - Keeping this as a modal as it acts as a focused dialog */}
      {uploadOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/80 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md rounded-2xl bg-zinc-900 border border-zinc-800 p-6 shadow-2xl animate-slide-up">
            <h2 className="text-lg font-semibold text-zinc-100 mb-4">Upload Job Description</h2>

            <label className="block mb-6">
              <span className="text-sm font-medium text-zinc-400 mb-2 block">PDF Document</span>
              <input
                ref={fileRef}
                type="file"
                accept="application/pdf"
                onChange={handleFileChange}
                className="block w-full text-sm text-zinc-400 file:mr-4 file:rounded-md file:border-0 file:bg-orange-500/10 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-orange-400 hover:file:bg-orange-500/20 transition-colors cursor-pointer"
              />
            </label>

            <div className="flex justify-end gap-3 mt-4">
              <button
                onClick={() => { setUploadOpen(false); setSelectedFile(null); }}
                className="rounded-lg px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
              >
                Cancel
              </button>
              <button
                disabled={!selectedFile || upload.isPending}
                onClick={handleUpload}
                className="rounded-lg bg-orange-600 px-4 py-2 text-sm font-semibold text-white hover:bg-orange-500 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-colors flex items-center gap-2"
              >
                {upload.isPending && <Loader2 size={14} className="animate-spin" />}
                Upload
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Manual Slide-over */}
      <Drawer
        isOpen={slideOverOpen}
        onClose={() => setSlideOverOpen(false)}
        title="Create Position Manually"
        size="md"
      >
        <ManualPositionForm onClose={() => setSlideOverOpen(false)} />
      </Drawer>

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
              <RefreshCw size={24} />
            </div>
          ) : (
            <div className="w-12 h-12 bg-zinc-800 text-zinc-400 rounded-full flex items-center justify-center mb-4">
              <RefreshCw size={24} />
            </div>
          )}
          <p className="text-zinc-300 text-base mb-8 max-w-sm text-center whitespace-pre-wrap">
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

    </div>
  )
}

function BriefcaseIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect width="20" height="14" x="2" y="7" rx="2" ry="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
    </svg>
  )
}
