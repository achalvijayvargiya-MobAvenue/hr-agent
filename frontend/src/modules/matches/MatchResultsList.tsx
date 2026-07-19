import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { MatchEntry, MatchResponse, ScoreBreakdown } from './hooks/useMatches'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../../components/ui/Table'
import { ChevronDown, ChevronUp, ExternalLink, ShieldAlert } from 'lucide-react'

// ── Source badge ────────────────────────────────────────────────────────────────

const SOURCE_STYLES: Record<string, string> = {
  local_kb: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  github: 'bg-zinc-800 text-zinc-300 border-zinc-700',
}

function SourceBadge({ source }: { source: string | null }) {
  if (!source) return null
  const style = SOURCE_STYLES[source] ?? 'bg-zinc-800 text-zinc-400 border-zinc-700'
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium capitalize border ${style}`}>
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
      <div className="w-full min-w-[120px]">
        <div className="flex h-1.5 w-full rounded-full overflow-hidden gap-0.5 bg-zinc-800/50 mb-1">
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
    <div className="w-full min-w-[120px]">
      <div className="flex h-1.5 w-full rounded-full overflow-hidden gap-0.5 bg-zinc-800/50 mb-1">
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
    </div>
  )
}

// ── Match Table Row ──────────────────────────────────────────────────────────

function MatchRow({ entry }: { entry: MatchEntry }) {
  const [expanded, setExpanded] = useState(false)
  const candidateUrl = `/candidates/${encodeURIComponent(entry.candidate_id)}`
  const finalScore = entry.final_score != null ? (entry.final_score * 100).toFixed(0) : 0
  
  const rankClass = entry.rank === 1
    ? 'bg-orange-500/10 text-orange-400 border-orange-500/20'
    : entry.rank === 2
    ? 'bg-zinc-300/10 text-zinc-300 border-zinc-400/20'
    : entry.rank === 3
    ? 'bg-orange-900/20 text-orange-600 border-orange-900/30'
    : 'bg-zinc-800/50 text-zinc-400 border-zinc-700'

  return (
    <>
      <TableRow className="group transition-colors">
        <TableCell className="w-16">
          <div className={`flex items-center justify-center px-2 py-1 rounded text-xs font-bold uppercase border ${rankClass}`}>
            #{entry.rank}
          </div>
        </TableCell>
        <TableCell>
          <div className="flex flex-col">
            <Link
              to={candidateUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="font-bold text-zinc-100 hover:text-orange-400 transition-colors flex items-center gap-1.5"
            >
              {entry.candidate_name ?? 'Unknown'}
              <ExternalLink size={12} className="opacity-0 group-hover:opacity-100 transition-opacity" />
            </Link>
            <div className="mt-1 flex gap-1.5 items-center flex-wrap">
              <SourceBadge source={entry.source_name} />
              {entry.switch_frequency != null && entry.switch_frequency > 0 && (
                <span className="text-[10px] text-zinc-500">
                  Avg Tenure: {entry.switch_frequency.toFixed(1)} yr
                </span>
              )}
            </div>
          </div>
        </TableCell>
        <TableCell>
          {entry.matched_preferred_companies != null && entry.matched_preferred_companies.length > 0 ? (
            <span className="inline-flex items-center rounded border border-green-700/50 bg-green-900/30 px-2 py-0.5 text-[10px] font-medium text-green-400" title="Worked at preferred companies">
              {entry.matched_preferred_companies.join(', ')}
            </span>
          ) : (
            <span className="text-zinc-500 text-xs">—</span>
          )}
        </TableCell>
        <TableCell>
          <div className="flex flex-col gap-1 items-end sm:items-start max-w-[150px]">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-zinc-100">{finalScore}%</span>
            </div>
            {entry.score_breakdown && <ScoreBar breakdown={entry.score_breakdown} />}
          </div>
        </TableCell>
        <TableCell className="text-right">
          {entry.explanation && (
            <button
              onClick={() => setExpanded((e) => !e)}
              className="inline-flex items-center gap-1 text-xs font-medium text-orange-400 hover:text-orange-300 transition-colors px-2 py-1 rounded bg-orange-500/10 hover:bg-orange-500/20"
            >
              {expanded ? 'Hide Details' : 'AI Analysis'}
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          )}
        </TableCell>
      </TableRow>
      
      {/* Expanded row for AI assessment */}
      {expanded && entry.explanation && (
        <TableRow className="bg-zinc-900/40 hover:bg-zinc-900/40 border-t-0">
          <TableCell colSpan={5} className="p-0 border-b border-zinc-800">
            <div className="p-4 pl-20 animate-fade-in">
              <div className="flex items-start gap-3 bg-zinc-950/80 rounded-lg p-4 border border-zinc-800/80 shadow-inner">
                <ShieldAlert size={16} className="text-orange-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">AI Assessment</h4>
                  <p className="text-sm text-zinc-300 leading-relaxed">
                    {entry.explanation}
                  </p>
                </div>
              </div>
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

// ── Filtered candidates section ─────────────────────────────────────────────────

function FilteredSection({ entries }: { entries: MatchEntry[] }) {
  const [open, setOpen] = useState(false)
  if (!entries.length) return null

  return (
    <div className="mt-8">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 text-sm font-medium text-zinc-500 hover:text-zinc-300 transition-colors"
      >
        <span className="inline-flex items-center justify-center rounded-full bg-red-500/10 text-red-400 border border-red-500/20 text-xs font-bold px-2 h-5">
          {entries.length} Filtered
        </span>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {open && (
        <div className="mt-3 animate-fade-in">
          <Table>
            <TableHeader className="bg-red-500/5">
              <tr>
                <TableHead className="text-red-400 w-1/3">Candidate</TableHead>
                <TableHead className="text-red-400">Gaps / Reason</TableHead>
              </tr>
            </TableHeader>
            <TableBody>
              {entries.map((e) => {
                const candidateUrl = `/candidates/${encodeURIComponent(e.candidate_id)}`
                return (
                  <TableRow key={e.candidate_id}>
                    <TableCell className="font-medium text-zinc-100">
                      <Link
                        to={candidateUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-orange-400 transition-colors inline-flex items-center gap-1.5"
                      >
                        {e.candidate_name ?? e.candidate_id}
                        <ExternalLink size={12} className="opacity-50" />
                      </Link>
                    </TableCell>
                    <TableCell className="text-red-400/90">
                      {e.requirement_gaps && e.requirement_gaps.length > 0 ? (
                        <ul className="list-disc list-inside space-y-1 text-sm">
                          {e.requirement_gaps.map((g, i) => (
                            <li key={i}>{g}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-sm">{e.filter_reason ?? '—'}</span>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
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
    <div className="animate-slide-up">
      {/* Header */}
      <div className="mb-4 flex items-baseline justify-between px-1">
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
        <p className="text-zinc-500 text-sm glass-panel p-6 text-center rounded-xl">
          No ranked results. Make sure candidates are embedded before running matching.
        </p>
      )}

      {/* Ranked Table */}
      {ranked.length > 0 && (
        <Table>
          <TableHeader>
            <tr>
              <TableHead>Rank</TableHead>
              <TableHead>Candidate</TableHead>
              <TableHead>Preferred Exp</TableHead>
              <TableHead>Match Score</TableHead>
              <TableHead className="text-right">Analysis</TableHead>
            </tr>
          </TableHeader>
          <TableBody>
            {ranked.map((entry) => (
              <MatchRow key={entry.candidate_id} entry={entry} />
            ))}
          </TableBody>
        </Table>
      )}

      {/* Filtered section */}
      <FilteredSection entries={filtered} />
    </div>
  )
}
