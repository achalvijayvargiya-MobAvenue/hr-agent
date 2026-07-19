import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { MatchEntry, MatchResponse, ScoreBreakdown } from './hooks/useMatches'

// ── Source badge ────────────────────────────────────────────────────────────────

const SOURCE_STYLES: Record<string, string> = {
  local_kb: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
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
      <div className="space-y-2 mt-2">
        <div className="flex h-3.5 w-full rounded-full overflow-hidden gap-0.5 bg-zinc-800/50">
          {fitPct > 0 && (
            <div
              className="bg-emerald-500 transition-all shadow-[0_0_8px_rgba(16,185,129,0.4)]"
              style={{ width: `${fitPct}%` }}
              title={`Requirement Fit: ${(breakdown.requirement_fit_score ?? 0).toFixed(2)}`}
            />
          )}
          {retPct > 0 && (
            <div
              className="bg-sky-400 transition-all shadow-[0_0_8px_rgba(56,189,248,0.4)]"
              style={{ width: `${retPct}%` }}
              title={`Semantic Match: ${(breakdown.vector_score ?? 0).toFixed(2)}`}
            />
          )}
          {rerPct > 0 && (
            <div
              className="bg-orange-500 transition-all shadow-[0_0_8px_rgba(249,115,22,0.4)]"
              style={{ width: `${rerPct}%` }}
              title={`AI Assessment: ${(breakdown.rerank_score ?? 0).toFixed(2)}`}
            />
          )}
        </div>
        <div className="flex gap-4 text-xs font-medium text-zinc-400">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_4px_rgba(16,185,129,0.6)]" />
            Requirement Fit {breakdown.requirement_fit_score != null ? breakdown.requirement_fit_score.toFixed(2) : '—'}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 rounded-full bg-sky-400 shadow-[0_0_4px_rgba(56,189,248,0.6)]" />
            Semantic Match {breakdown.vector_score != null ? breakdown.vector_score.toFixed(2) : '—'}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 rounded-full bg-orange-500 shadow-[0_0_4px_rgba(249,115,22,0.6)]" />
            AI Assessment {breakdown.rerank_score != null ? breakdown.rerank_score.toFixed(2) : '—'}
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
    <div className="space-y-2 mt-2">
      <div className="flex h-3.5 w-full rounded-full overflow-hidden gap-0.5 bg-zinc-800/50">
        {rPct > 0 && (
          <div
            className="bg-emerald-500 transition-all shadow-[0_0_8px_rgba(16,185,129,0.4)]"
            style={{ width: `${rPct}%` }}
            title={`Requirement Fit: ${(rule_score ?? 0).toFixed(2)}`}
          />
        )}
        {vPct > 0 && (
          <div
            className="bg-sky-400 transition-all shadow-[0_0_8px_rgba(56,189,248,0.4)]"
            style={{ width: `${vPct}%` }}
            title={`Semantic Match: ${(vector_score ?? 0).toFixed(2)}`}
          />
        )}
        {lPct > 0 && (
          <div
            className="bg-orange-500 transition-all shadow-[0_0_8px_rgba(249,115,22,0.4)]"
            style={{ width: `${lPct}%` }}
            title={`AI Assessment: ${(llm_score ?? 0).toFixed(2)}`}
          />
        )}
      </div>
      <div className="flex gap-4 text-xs font-medium text-zinc-400">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_4px_rgba(16,185,129,0.6)]" />
            Requirement Fit {rule_score != null ? rule_score.toFixed(2) : '—'}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded-full bg-sky-400 shadow-[0_0_4px_rgba(56,189,248,0.6)]" />
            Semantic Match {vector_score != null ? vector_score.toFixed(2) : '—'}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded-full bg-orange-500 shadow-[0_0_4px_rgba(249,115,22,0.6)]" />
            AI Assessment {llm_score != null ? llm_score.toFixed(2) : '—'}
        </span>
      </div>
    </div>
  )
}

// ── Single ranked card ──────────────────────────────────────────────────────────

function MatchCard({ entry }: { entry: MatchEntry }) {
  const [expanded, setExpanded] = useState(false)
  const candidateUrl = `/candidates/${encodeURIComponent(entry.candidate_id)}`
  const finalScore = entry.final_score != null ? (entry.final_score * 100).toFixed(0) : 0
  const circumference = 2 * Math.PI * 18 // r=18
  const strokeDashoffset = circumference - ((Number(finalScore) / 100) * circumference)

  return (
    <div className="glass-panel rounded-xl p-5 flex gap-5 items-start hover:-translate-y-0.5 transition-transform">
      {/* Rank badge */}
      <div className="flex-shrink-0 mt-1">
        <div
          className={`flex items-center justify-center px-3 py-1 rounded-md text-xs font-bold uppercase tracking-wider border ${
            entry.rank === 1
              ? 'bg-orange-500/10 text-orange-400 border-orange-500/20'
              : entry.rank === 2
              ? 'bg-zinc-300/10 text-zinc-300 border-zinc-400/20'
              : entry.rank === 3
              ? 'bg-orange-900/20 text-orange-600 border-orange-900/30'
              : 'bg-zinc-800/50 text-zinc-400 border-zinc-700'
          }`}
        >
          Rank #{entry.rank}
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-4">
          <div>
            <Link
              to={candidateUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-lg font-bold text-zinc-100 hover:text-orange-400 transition-colors"
            >
              {entry.candidate_name ?? 'Unknown'}
            </Link>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <SourceBadge source={entry.source_name} />
              {entry.switch_frequency != null && entry.switch_frequency > 0 && (
                <span className="inline-flex items-center rounded border border-zinc-700 bg-zinc-800/50 px-2 py-0.5 text-xs font-medium text-zinc-400" title="Average Tenure (Years per Company)">
                  Avg Tenure: {entry.switch_frequency.toFixed(1)} yrs/company
                </span>
              )}
              {entry.matched_preferred_companies != null && entry.matched_preferred_companies.length > 0 && (
                <span className="inline-flex items-center rounded border border-green-700/50 bg-green-900/30 px-2 py-0.5 text-xs font-medium text-green-400" title="Worked at preferred companies">
                  Preferred Exp: {entry.matched_preferred_companies.join(', ')}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-4 flex-shrink-0">
            <Link
              to={candidateUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
            >
              View Profile
            </Link>
            <div className="relative flex items-center justify-center w-14 h-14" title={`Final Score: ${entry.final_score?.toFixed(2)}`}>
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 44 44">
                <circle cx="22" cy="22" r="18" fill="none" stroke="currentColor" strokeWidth="4" className="text-zinc-800" />
                <circle
                  cx="22" cy="22" r="18" fill="none" stroke="currentColor" strokeWidth="4"
                  className="text-orange-500 drop-shadow-[0_0_4px_rgba(249,115,22,0.6)]"
                  strokeDasharray={circumference}
                  strokeDashoffset={strokeDashoffset}
                  strokeLinecap="round"
                />
              </svg>
              <span className="absolute text-sm font-bold text-zinc-100">{finalScore}<span className="text-[10px]">%</span></span>
            </div>
          </div>
        </div>

        {/* Score breakdown bar */}
        {entry.score_breakdown && <ScoreBar breakdown={entry.score_breakdown} />}

        {/* Explanation (collapsible) */}
        {entry.explanation && (
          <div className="mt-4">
            <button
              onClick={() => setExpanded((e) => !e)}
              className="flex items-center gap-1 text-xs text-orange-400 hover:text-orange-300 font-medium transition-colors"
            >
              {expanded ? (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3 h-3"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" /></svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3 h-3"><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>
              )}
              {expanded ? 'Hide AI assessment' : 'Show AI assessment'}
            </button>
            {expanded && (
              <p className="mt-2 text-sm text-zinc-300 leading-relaxed bg-zinc-950/50 rounded-lg p-3 border border-zinc-800/50 shadow-inner">
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
                      className="hover:text-orange-400 transition-colors"
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
          <span className="text-orange-400">{positionTitle}</span>
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
