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
  in_pool: 'bg-green-100 text-green-800',
  manual_add: 'bg-blue-100 text-blue-800',
  out_of_pool: 'bg-gray-100 text-gray-600',
  manual_exclude: 'bg-red-100 text-red-700',
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
    <tr className={inPool ? '' : 'opacity-60'}>
      <td className="px-4 py-2 text-sm">
        <Link
          to={`/candidates/${encodeURIComponent(entry.candidate_id)}`}
          className="font-medium text-gray-900 hover:text-indigo-600"
        >
          {entry.candidate_name ?? entry.candidate_id}
        </Link>
        {entry.current_title && (
          <p className="text-xs text-gray-500">{entry.current_title}</p>
        )}
      </td>
      <td className="px-4 py-2 text-sm text-gray-600">
        {entry.domain_code ?? '—'}
        {entry.subdomain_codes.length > 0 && (
          <p className="text-xs text-gray-400">{entry.subdomain_codes.join(', ')}</p>
        )}
      </td>
      <td className="px-4 py-2 text-sm font-medium text-gray-800">
        {(entry.relevance_score * 100).toFixed(0)}%
      </td>
      <td className="px-4 py-2">
        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[entry.pool_status] ?? 'bg-gray-100'}`}
        >
          {entry.pool_status.replace(/_/g, ' ')}
        </span>
      </td>
      <td className="px-4 py-2 text-xs text-gray-500 max-w-xs truncate" title={entry.match_reason ?? ''}>
        {entry.match_reason ?? '—'}
      </td>
      <td className="px-4 py-2 text-right">
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
              className="text-xs text-blue-600 hover:underline"
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
              className="text-xs text-red-600 hover:underline"
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
              className="text-xs text-gray-500 hover:underline"
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
    <div className="mt-6 bg-white rounded-xl border border-emerald-200 shadow-sm p-6 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-emerald-800">Candidate Pool</h2>
          <p className="text-sm text-gray-500 mt-1">
            Domain-based grouping — only relevant candidates appear here before matching.
          </p>
        </div>
        <button
          onClick={handleBuild}
          disabled={buildPool.isPending || isFetching}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {buildPool.isPending ? 'Building…' : activePool ? 'Rebuild Pool' : 'Build Pool'}
        </button>
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {activePool && (
        <div className="flex flex-wrap gap-4 text-sm">
          <span>
            <strong className="text-emerald-700">{activePool.in_pool}</strong> in pool
          </span>
          <span className="text-gray-400">·</span>
          <span>{activePool.out_of_pool} excluded</span>
          <span className="text-gray-400">·</span>
          <span>{activePool.total_candidates} total evaluated</span>
          {activePool.computed_at && (
            <>
              <span className="text-gray-400">·</span>
              <span className="text-gray-400 text-xs">
                built {new Date(activePool.computed_at).toLocaleString()}
              </span>
            </>
          )}
        </div>
      )}

      {!activePool && !buildPool.isPending && (
        <p className="text-sm text-gray-400">
          Set domain above, then click Build Pool to group relevant candidates.
        </p>
      )}

      {displayed.length > 0 && (
        <>
          <div className="flex justify-between items-center">
            <p className="text-sm font-medium text-gray-700">
              {showAll ? 'All candidates' : 'In pool'} ({displayed.length})
            </p>
            <button
              onClick={() => setShowAll((v) => !v)}
              className="text-xs text-emerald-600 hover:underline"
            >
              {showAll ? 'Show in-pool only' : `Show all (${entries.length})`}
            </button>
          </div>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-100">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase text-gray-500">Candidate</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase text-gray-500">Domain</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase text-gray-500">Relevance</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase text-gray-500">Status</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase text-gray-500">Reason</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold uppercase text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 bg-white">
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
