import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { MatchEntry, MatchResponse, ScoreBreakdown } from './hooks/useMatches'

// ── Source badge ────────────────────────────────────────────────────────────────

const SOURCE_STYLES: Record<string, string> = {
  local_kb: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
  github: 'bg-zinc-800 text-zinc-300 border-zinc-700',
}

function SourceBadge({ source }: { source: string | null }) {
  if (!source) return null
  const style = SOURCE_STYLES[source] ?? 'bg-zinc-800 text-zinc-400 border-zinc-700'
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize border ${style}`}>
      {source.replace(/_/g, ' ')}
    </span>
  )
}

// ── Score breakdown bar ─────────────────────────────────────────────────────────

function ScoreBar({ breakdown }: { breakdown: ScoreBreakdown }) {
  const phase4 = breakdown.rerank_weight != null && breakdown.rerank_weight > 0

  if (phase4) {
    const fitContrib =
      (breakdown.requirement_fit_score ?? 0) * (breakdown.requirement_fit_weight ?? 0)
    const retrievalContrib = (breakdown.vector_score ?? 0) * breakdown.vector_weight
    const rerankContrib = (breakdown.rerank_score ?? 0) * (breakdown.rerank_weight ?? 0)
    const total = fitContrib + retrievalContrib + rerankContrib || 1

    const fitPct = (fitContrib / total) * 100
    const retPct = (retrievalContrib / total) * 100
    const rerPct = (rerankContrib / total) * 100

    return (
      <div className="space-y-1">
        <div className="flex h-3 rounded-full overflow-hidden gap-px bg-zinc-800">
          {fitPct > 0 && (
            <div
              className="bg-emerald-500 transition-all shadow-[0_0_8px_rgba(16,185,129,0.6)]"
              style={{ width: `${fitPct}%` }}
              title={`Fit: ${(breakdown.requirement_fit_score ?? 0).toFixed(2)} × ${((breakdown.requirement_fit_weight ?? 0) * 100).toFixed(0)}%`}
            />
          )}
          {retPct > 0 && (
            <div
              className="bg-sky-400 transition-all shadow-[0_0_8px_rgba(56,189,248,0.6)]"
              style={{ width: `${retPct}%` }}
              title={`Retrieval: ${(breakdown.vector_score ?? 0).toFixed(2)} × ${(breakdown.vector_weight * 100).toFixed(0)}%`}
            />
          )}
          {rerPct > 0 && (
            <div
              className="bg-violet-500 transition-all shadow-[0_0_8px_rgba(139,92,246,0.6)]"
              style={{ width: `${rerPct}%` }}
              title={`Rerank: ${(breakdown.rerank_score ?? 0).toFixed(2)} × ${((breakdown.rerank_weight ?? 0) * 100).toFixed(0)}%`}
            />
          )}
        </div>
        <div className="flex gap-3 text-xs text-zinc-400">
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-sm bg-emerald-500 shadow-[0_0_4px_rgba(16,185,129,0.6)]" />
            Fit {breakdown.requirement_fit_score != null ? breakdown.requirement_fit_score.toFixed(2) : '—'}
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-sm bg-sky-400 shadow-[0_0_4px_rgba(56,189,248,0.6)]" />
            Retrieval {breakdown.vector_score != null ? breakdown.vector_score.toFixed(2) : '—'}
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-sm bg-violet-500 shadow-[0_0_4px_rgba(139,92,246,0.6)]" />
            Rerank {breakdown.rerank_score != null ? breakdown.rerank_score.toFixed(2) : '—'}
          </span>
        </div>
      </div>
    )
  }

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
      <div className="flex h-3 rounded-full overflow-hidden gap-px bg-zinc-800">
        {rPct > 0 && (
          <div
            className="bg-indigo-500 transition-all shadow-[0_0_8px_rgba(99,102,241,0.6)]"
            style={{ width: `${rPct}%` }}
            title={`Rule: ${(rule_score ?? 0).toFixed(2)} × ${(rule_weight * 100).toFixed(0)}%`}
          />
        )}
        {vPct > 0 && (
          <div
            className="bg-sky-400 transition-all shadow-[0_0_8px_rgba(56,189,248,0.6)]"
            style={{ width: `${vPct}%` }}
            title={`Vector: ${(vector_score ?? 0).toFixed(2)} × ${(vector_weight * 100).toFixed(0)}%`}
          />
        )}
        {lPct > 0 && (
          <div
            className="bg-violet-500 transition-all shadow-[0_0_8px_rgba(139,92,246,0.6)]"
            style={{ width: `${lPct}%` }}
            title={`LLM: ${(llm_score ?? 0).toFixed(2)} × ${(llm_weight * 100).toFixed(0)}%`}
          />
        )}
      </div>
      <div className="flex gap-3 text-xs text-zinc-400">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-sm bg-indigo-500 shadow-[0_0_4px_rgba(99,102,241,0.6)]" />
          Rule {rule_score != null ? rule_score.toFixed(2) : '—'}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-sm bg-sky-400 shadow-[0_0_4px_rgba(56,189,248,0.6)]" />
          Vector {vector_score != null ? vector_score.toFixed(2) : '—'}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-sm bg-violet-500 shadow-[0_0_4px_rgba(139,92,246,0.6)]" />
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
    <div className="glass-panel rounded-xl p-5 flex gap-4 hover:-translate-y-0.5 transition-transform">
      {/* Rank badge */}
      <div className="flex-shrink-0 flex items-start justify-center">
        <span
          className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold text-white shadow-lg ${
            entry.rank === 1
              ? 'bg-amber-500 shadow-amber-500/50'
              : entry.rank === 2
              ? 'bg-zinc-400 shadow-zinc-400/50'
              : entry.rank === 3
              ? 'bg-amber-700 shadow-amber-700/50'
              : 'bg-indigo-500 shadow-indigo-500/50'
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
              className="text-base font-semibold text-zinc-100 hover:text-indigo-400 transition-colors"
            >
              {entry.candidate_name ?? 'Unknown'}
            </Link>
            <div className="flex items-center gap-2 mt-0.5">
              <SourceBadge source={entry.source_name} />
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-2xl font-bold text-indigo-400 drop-shadow-[0_0_8px_rgba(99,102,241,0.5)]">
              {entry.final_score != null ? entry.final_score.toFixed(2) : '—'}
            </p>
            <p className="text-xs text-zinc-500">final score</p>
          </div>
        </div>

        {entry.score_breakdown?.requirement_fit_score != null && (
          <p className="text-xs text-emerald-600 mt-1">
            Requirement fit: {(entry.score_breakdown.requirement_fit_score * 100).toFixed(0)}%
          </p>
        )}

        {/* Score breakdown bar */}
        {entry.score_breakdown && <ScoreBar breakdown={entry.score_breakdown} />}

        {/* Explanation (collapsible) */}
        {entry.explanation && (
          <div className="mt-3">
            <button
              onClick={() => setExpanded((e) => !e)}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
            >
              {expanded ? '▲ Hide explanation' : '▼ Show explanation'}
            </button>
            {expanded && (
              <p className="mt-2 text-sm text-zinc-300 leading-relaxed bg-zinc-950/50 rounded-lg p-3 border border-zinc-800/50">
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
        className="flex items-center gap-2 text-sm font-medium text-zinc-500 hover:text-zinc-300 transition-colors"
      >
        <span className="inline-flex items-center justify-center rounded-full bg-red-500/10 text-red-400 border border-red-500/20 text-xs font-bold w-5 h-5">
          {entries.length}
        </span>
        {open ? '▲ Hide' : '▼ Show'} filtered-out candidates
      </button>

      {open && (
        <div className="mt-3 glass-panel rounded-xl border border-red-500/20 overflow-hidden animate-fade-in">
          <table className="min-w-full divide-y divide-zinc-800">
            <thead className="bg-red-500/5">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-red-400">
                  Candidate
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-red-400">
                  Gaps / Reason
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800 bg-zinc-950/30">
              {entries.map((e) => {
                const candidateUrl = `/candidates/${encodeURIComponent(e.candidate_id)}`
                return (
                <tr key={e.candidate_id} className="hover:bg-zinc-800/50 transition-colors">
                  <td className="px-4 py-3 text-sm font-medium text-zinc-100">
                    <Link
                      to={candidateUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-indigo-400 transition-colors"
                    >
                      {e.candidate_name ?? e.candidate_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-sm text-red-400/90">
                    {e.requirement_gaps && e.requirement_gaps.length > 0 ? (
                      <ul className="list-disc list-inside space-y-0.5">
                        {e.requirement_gaps.map((g, i) => (
                          <li key={i}>{g}</li>
                        ))}
                      </ul>
                    ) : (
                      e.filter_reason ?? '—'
                    )}
                  </td>
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
        <h2 className="text-lg font-semibold text-zinc-100">
          Top {ranked.length} Candidates for{' '}
          <span className="text-indigo-400">{positionTitle}</span>
        </h2>
        <span className="text-xs text-zinc-500">
          {result.total_candidates} evaluated · computed{' '}
          {result.computed_at ? new Date(result.computed_at).toLocaleTimeString() : '—'}
        </span>
      </div>

      {ranked.length === 0 && (
        <p className="text-zinc-500 text-sm glass-panel p-4 rounded-xl">
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
