import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useBuildJobPool,
  useJobPool,
  useUpdatePoolMember,
  type PoolEntry,
} from './hooks/useDomain'

interface Props {
  positionId: string
}

const STATUS_STYLES: Record<string, string> = {
  in_pool: 'bg-orange-500/10 text-orange-400 border border-orange-500/20',
  manual_add: 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
  out_of_pool: 'bg-zinc-800 text-zinc-400 border border-zinc-700',
  manual_exclude: 'bg-red-500/10 text-red-400 border border-red-500/20',
}

function PoolRow({
  entry,
  positionId,
}: {
  entry: PoolEntry
  positionId: string
}) {
  const updateMember = useUpdatePoolMember()
  const inPool = entry.pool_status === 'in_pool' || entry.pool_status === 'manual_add'

  return (
    <tr className={`border-b border-zinc-800/50 ${inPool ? '' : 'opacity-60'}`}>
      <td className="px-4 py-3 text-sm">
        <Link
          to={`/candidates/${encodeURIComponent(entry.candidate_id)}`}
          className="font-medium text-zinc-100 hover:text-orange-400 transition-colors"
        >
          {entry.candidate_name ?? entry.candidate_id}
        </Link>
        {entry.current_title && (
          <p className="text-xs text-zinc-500">{entry.current_title}</p>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-zinc-400">
        {entry.domain_code ?? '—'}
        {entry.subdomain_codes.length > 0 && (
          <p className="text-xs text-zinc-500">{entry.subdomain_codes.join(', ')}</p>
        )}
      </td>
      <td className="px-4 py-3 text-sm font-medium text-zinc-100">
        {(entry.relevance_score * 100).toFixed(0)}%
      </td>
      <td className="px-4 py-3">
        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[entry.pool_status] ?? 'bg-zinc-800 text-zinc-400'}`}
        >
          {entry.pool_status.replace(/_/g, ' ')}
        </span>
      </td>
      <td className="px-4 py-3 text-xs text-zinc-500 max-w-xs truncate" title={entry.match_reason ?? ''}>
        {entry.match_reason ?? '—'}
      </td>
      <td className="px-4 py-3 text-right">
        <div className="flex gap-1 justify-end">
          {!inPool && (
            <button
              onClick={() =>
                updateMember.mutate({
                  jobId: positionId,
                  candidateId: entry.candidate_id,
                  pool_status: 'manual_add',
                })
              }
              disabled={updateMember.isPending}
              className="text-xs text-blue-400 hover:text-blue-300 hover:underline transition-colors"
            >
              Add
            </button>
          )}
          {inPool && entry.pool_status !== 'manual_add' && (
            <button
              onClick={() =>
                updateMember.mutate({
                  jobId: positionId,
                  candidateId: entry.candidate_id,
                  pool_status: 'manual_exclude',
                })
              }
              disabled={updateMember.isPending}
              className="text-xs text-red-400 hover:text-red-300 hover:underline transition-colors"
            >
              Exclude
            </button>
          )}
          {(entry.pool_status === 'manual_add' || entry.pool_status === 'manual_exclude') && (
            <button
              onClick={() =>
                updateMember.mutate({
                  jobId: positionId,
                  candidateId: entry.candidate_id,
                  pool_status: 'auto',
                })
              }
              disabled={updateMember.isPending}
              className="text-xs text-zinc-400 hover:text-zinc-300 hover:underline transition-colors"
            >
              Reset
            </button>
          )}
        </div>
      </td>
    </tr>
  )
}

export default function CandidatePoolPanel({ positionId }: Props) {
  const [showAll, setShowAll] = useState(false)
  const buildPool = useBuildJobPool()
  const { data: pool, isFetching, refetch } = useJobPool(positionId)

  function handleBuild() {
    buildPool.mutate(positionId, {
      onSuccess: () => {
        refetch()
      },
    })
  }

  const activePool = buildPool.data ?? pool
  const entries = activePool?.entries ?? []
  const inPoolEntries = entries.filter(
    (e) => e.pool_status === 'in_pool' || e.pool_status === 'manual_add',
  )
  const displayed = showAll ? entries : inPoolEntries

  const error =
    (buildPool.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail

  return (
    <div className="mt-6 glass-panel rounded-xl border border-orange-500/20 p-6 space-y-4 animate-slide-up animate-stagger-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-orange-400">Candidate Pool</h2>
          <p className="text-sm text-zinc-400 mt-1">
            Domain-based grouping — only relevant candidates appear here before matching.
          </p>
        </div>
        <button
          onClick={handleBuild}
          disabled={buildPool.isPending || isFetching}
          className="rounded-lg bg-orange-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-orange-900/50 hover:bg-orange-500 disabled:opacity-50 transition-colors"
        >
          {buildPool.isPending ? 'Building…' : activePool ? 'Rebuild Pool' : 'Build Pool'}
        </button>
      </div>

      {error && (
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 animate-slide-up">
          {error}
        </p>
      )}

      {activePool && (
        <div className="flex flex-wrap gap-4 text-sm bg-zinc-950/50 border border-zinc-800/50 rounded-lg p-3">
          <span>
            <strong className="text-orange-400">{activePool.in_pool}</strong> <span className="text-zinc-300">in pool</span>
          </span>
          <span className="text-zinc-600">·</span>
          <span className="text-zinc-400">{activePool.out_of_pool} excluded</span>
          <span className="text-zinc-600">·</span>
          <span className="text-zinc-400">{activePool.total_candidates} total evaluated</span>
          {activePool.computed_at && (
            <>
              <span className="text-zinc-600">·</span>
              <span className="text-zinc-500 text-xs">
                built {new Date(activePool.computed_at).toLocaleString()}
              </span>
            </>
          )}
        </div>
      )}

      {!activePool && !buildPool.isPending && (
        <p className="text-sm text-zinc-500">
          Set domain above, then click Build Pool to group relevant candidates.
        </p>
      )}

      {displayed.length > 0 && (
        <>
          <div className="flex justify-between items-center">
            <p className="text-sm font-medium text-zinc-300">
              {showAll ? 'All candidates' : 'In pool'} <span className="text-zinc-500">({displayed.length})</span>
            </p>
            <button
              onClick={() => setShowAll((v) => !v)}
              className="text-xs text-orange-400 hover:text-orange-300 hover:underline transition-colors"
            >
              {showAll ? 'Show in-pool only' : `Show all (${entries.length})`}
            </button>
          </div>
          <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950/30">
            <table className="min-w-full">
              <thead className="bg-zinc-900/50 border-b border-zinc-800">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-zinc-500 tracking-wider">Candidate</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-zinc-500 tracking-wider">Domain</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-zinc-500 tracking-wider">Relevance</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-zinc-500 tracking-wider">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-zinc-500 tracking-wider">Reason</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase text-zinc-500 tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {displayed.map((entry) => (
                  <PoolRow key={entry.candidate_id} entry={entry} positionId={positionId} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
