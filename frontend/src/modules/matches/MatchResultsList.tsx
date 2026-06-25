import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { MatchEntry, MatchResponse, ScoreBreakdown } from './hooks/useMatches'

// ── Source badge ────────────────────────────────────────────────────────────────

const SOURCE_STYLES: Record<string, string> = {
  local_kb: 'bg-blue-100 text-blue-800',
  github: 'bg-gray-800 text-white',
}

function SourceBadge({ source }: { source: string | null }) {
  if (!source) return null
  const style = SOURCE_STYLES[source] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${style}`}>
      {source.replace(/_/g, ' ')}
    </span>
  )
}

// ── Score breakdown bar ─────────────────────────────────────────────────────────

function ScoreBar({ breakdown }: { breakdown: ScoreBreakdown }) {
  const { rule_score, vector_score, llm_score, rule_weight, vector_weight, llm_weight } = breakdown

  const ruleContrib = (rule_score ?? 0) * rule_weight
  const vectorContrib = (vector_score ?? 0) * vector_weight
  const llmContrib = (llm_score ?? 0) * llm_weight
  const total = ruleContrib + vectorContrib + llmContrib || 1

  const rPct = (ruleContrib / total) * 100
  const vPct = (vectorContrib / total) * 100
  const lPct = (llmContrib / total) * 100

  return (
    <div className="space-y-1">
      <div className="flex h-3 rounded-full overflow-hidden gap-px bg-gray-100">
        {rPct > 0 && (
          <div
            className="bg-indigo-500 transition-all"
            style={{ width: `${rPct}%` }}
            title={`Rule: ${(rule_score ?? 0).toFixed(2)} × ${(rule_weight * 100).toFixed(0)}%`}
          />
        )}
        {vPct > 0 && (
          <div
            className="bg-sky-400 transition-all"
            style={{ width: `${vPct}%` }}
            title={`Vector: ${(vector_score ?? 0).toFixed(2)} × ${(vector_weight * 100).toFixed(0)}%`}
          />
        )}
        {lPct > 0 && (
          <div
            className="bg-violet-500 transition-all"
            style={{ width: `${lPct}%` }}
            title={`LLM: ${(llm_score ?? 0).toFixed(2)} × ${(llm_weight * 100).toFixed(0)}%`}
          />
        )}
      </div>
      <div className="flex gap-3 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-sm bg-indigo-500" />
          Rule {rule_score != null ? rule_score.toFixed(2) : '—'}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-sm bg-sky-400" />
          Vector {vector_score != null ? vector_score.toFixed(2) : '—'}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-sm bg-violet-500" />
          LLM {llm_score != null ? llm_score.toFixed(2) : '—'}
        </span>
      </div>
    </div>
  )
}

// ── Single ranked card ──────────────────────────────────────────────────────────

function MatchCard({ entry }: { entry: MatchEntry }) {
  const [expanded, setExpanded] = useState(false)
  const candidateUrl = `/candidates/${encodeURIComponent(entry.candidate_id)}`

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex gap-4">
      {/* Rank badge */}
      <div className="flex-shrink-0 flex items-start justify-center">
        <span
          className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold text-white ${
            entry.rank === 1
              ? 'bg-amber-400'
              : entry.rank === 2
              ? 'bg-gray-400'
              : entry.rank === 3
              ? 'bg-amber-600'
              : 'bg-indigo-400'
          }`}
        >
          #{entry.rank}
        </span>
      </div>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <Link
              to={candidateUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-base font-semibold text-gray-900 hover:text-indigo-600"
            >
              {entry.candidate_name ?? 'Unknown'}
            </Link>
            <div className="flex items-center gap-2 mt-0.5">
              <SourceBadge source={entry.source_name} />
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-2xl font-bold text-indigo-600">
              {entry.final_score != null ? entry.final_score.toFixed(2) : '—'}
            </p>
            <p className="text-xs text-gray-400">final score</p>
          </div>
        </div>

        {/* Score breakdown bar */}
        {entry.score_breakdown && <ScoreBar breakdown={entry.score_breakdown} />}

        {/* Explanation (collapsible) */}
        {entry.explanation && (
          <div className="mt-3">
            <button
              onClick={() => setExpanded((e) => !e)}
              className="text-xs text-indigo-500 hover:text-indigo-700 font-medium"
            >
              {expanded ? '▲ Hide explanation' : '▼ Show explanation'}
            </button>
            {expanded && (
              <p className="mt-2 text-sm text-gray-600 leading-relaxed bg-gray-50 rounded-lg p-3 border border-gray-100">
                {entry.explanation}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Filtered candidates section ─────────────────────────────────────────────────

function FilteredSection({ entries }: { entries: MatchEntry[] }) {
  const [open, setOpen] = useState(false)
  if (!entries.length) return null

  return (
    <div className="mt-4">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-gray-700"
      >
        <span className="inline-flex items-center justify-center rounded-full bg-red-100 text-red-700 text-xs font-bold w-5 h-5">
          {entries.length}
        </span>
        {open ? '▲ Hide' : '▼ Show'} filtered-out candidates
      </button>

      {open && (
        <div className="mt-3 bg-white rounded-xl border border-red-100 shadow-sm overflow-hidden">
          <table className="min-w-full divide-y divide-gray-100">
            <thead className="bg-red-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-red-600">
                  Candidate
                </th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-red-600">
                  Filter Reason
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {entries.map((e) => {
                const candidateUrl = `/candidates/${encodeURIComponent(e.candidate_id)}`
                return (
                <tr key={e.candidate_id}>
                  <td className="px-4 py-2 text-sm text-gray-700">
                    <Link
                      to={candidateUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-indigo-600"
                    >
                      {e.candidate_name ?? e.candidate_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-sm text-red-600">{e.filter_reason ?? '—'}</td>
                </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Main export ─────────────────────────────────────────────────────────────────

interface Props {
  result: MatchResponse
  positionTitle: string
  topK: number
}

export default function MatchResultsList({ result, positionTitle, topK }: Props) {
  const ranked = result.matches.filter((m) => !m.is_filtered).slice(0, topK)
  const filtered = result.matches.filter((m) => m.is_filtered)

  return (
    <div>
      {/* Header */}
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-gray-800">
          Top {ranked.length} Candidates for{' '}
          <span className="text-indigo-600">{positionTitle}</span>
        </h2>
        <span className="text-xs text-gray-400">
          {result.total_candidates} evaluated · computed{' '}
          {result.computed_at ? new Date(result.computed_at).toLocaleTimeString() : '—'}
        </span>
      </div>

      {ranked.length === 0 && (
        <p className="text-gray-400 text-sm">
          No ranked results. Make sure candidates are embedded before running matching.
        </p>
      )}

      {/* Ranked cards */}
      <div className="space-y-3">
        {ranked.map((entry) => (
          <MatchCard key={entry.candidate_id} entry={entry} />
        ))}
      </div>

      {/* Filtered section */}
      <FilteredSection entries={filtered} />
    </div>
  )
}
