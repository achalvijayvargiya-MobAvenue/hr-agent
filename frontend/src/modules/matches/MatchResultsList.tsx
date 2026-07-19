import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { MatchEntry, MatchResponse, ScoreBreakdown } from './hooks/useMatches'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../../components/ui/Table'
import { ChevronDown, ChevronUp, ExternalLink, ShieldAlert, ChevronRight } from 'lucide-react'

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

// ── Circular Progress ────────────────────────────────────────────────────────
function CircularProgress({ percentage }: { percentage: number }) {
  const radius = 16
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (percentage / 100) * circumference
  
  // Determine color based on percentage
  const colorClass = percentage >= 80 ? 'text-emerald-500' : percentage >= 60 ? 'text-orange-500' : 'text-zinc-400'

  return (
    <div className="relative flex items-center justify-center w-10 h-10">
      <svg className="transform -rotate-90 w-10 h-10">
        <circle cx="20" cy="20" r={radius} className="text-zinc-800" strokeWidth="3" fill="transparent" stroke="currentColor" />
        <circle 
          cx="20" cy="20" r={radius} 
          className={`${colorClass} transition-all duration-1000 ease-out`} 
          strokeWidth="3" fill="transparent" 
          strokeDasharray={circumference} 
          strokeDashoffset={strokeDashoffset} 
          stroke="currentColor" strokeLinecap="round" 
        />
      </svg>
      <span className="absolute text-[10px] font-bold text-white">{percentage}</span>
    </div>
  )
}

// ── Match Table Row ──────────────────────────────────────────────────────────

function MatchRow({ entry, index }: { entry: MatchEntry; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const candidateUrl = `/candidates/${encodeURIComponent(entry.candidate_id)}`
  const finalScore = entry.final_score != null ? (entry.final_score * 100).toFixed(0) : 0

  let aiData: any = null
  let aiText = entry.explanation
  if (entry.explanation) {
    try {
      const parsed = JSON.parse(entry.explanation)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        aiData = parsed
        aiText = parsed.explanation || entry.explanation
      }
    } catch (e) {
      // Fallback to plain text
    }
  }

  const rankClass = entry.rank === 1
    ? 'text-amber-500 border-amber-500/30 bg-amber-500/10 shadow-[0_0_8px_rgba(245,158,11,0.1)]'
    : entry.rank === 2
    ? 'bg-zinc-300/10 text-zinc-300 border-zinc-400/20'
    : entry.rank === 3
    ? 'bg-orange-900/20 text-orange-600 border-orange-900/30'
    : 'bg-zinc-800/50 text-zinc-400 border-zinc-700'

  return (
    <>
      <TableRow 
        className="group transition-all duration-300 bg-zinc-950/20 hover:bg-zinc-800/40 border-b border-zinc-800/50"
        style={{ animation: `fadeIn 0.5s ease-out ${index * 150}ms both` }}
      >
        <TableCell className="w-20 align-middle">
          <div className="flex items-center justify-center">
            <div className={`flex items-center justify-center px-2 py-1 rounded text-sm font-bold uppercase border ${rankClass}`}>
              #{entry.rank}
            </div>
          </div>
        </TableCell>
        <TableCell className="align-middle py-3">
          <div className="flex flex-col py-1">
            <div className="flex items-center gap-2">
              <Link
                to={candidateUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-lg font-bold text-zinc-100 hover:text-orange-400 transition-colors flex items-center gap-2"
              >
                {entry.candidate_name ?? 'Unknown'}
                <ExternalLink size={14} className="opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
              {entry.requirement_gaps && entry.requirement_gaps.length > 0 && (
                <div title={`Missing Requirements:\n${entry.requirement_gaps.join('\n')}`} className="flex items-center text-red-500 bg-red-500/10 rounded-full p-1.5 cursor-help">
                  <ShieldAlert size={16} />
                </div>
              )}
            </div>
            <div className="mt-2 flex gap-2 items-center flex-wrap">
              <SourceBadge source={entry.source_name} />
              {entry.years_experience != null && entry.years_experience > 0 && (
                <span className="text-xs text-zinc-300 font-bold bg-zinc-800 px-2 py-0.5 rounded">
                  {entry.years_experience.toFixed(1)} yr Exp
                </span>
              )}
              {entry.switch_frequency != null && entry.switch_frequency > 0 && (
                <span className="text-xs text-zinc-300 font-bold bg-zinc-800 px-2 py-0.5 rounded">
                  Avg Tenure: {entry.switch_frequency.toFixed(1)} yr
                </span>
              )}
              {entry.matched_preferred_companies != null && entry.matched_preferred_companies.length > 0 && (
                <span className="inline-flex items-center rounded border border-emerald-400/30 bg-zinc-800 px-2 py-0.5 text-xs font-medium text-emerald-400 shadow-sm" title="Worked at preferred companies">
                  ✨ Preferred Company: {entry.matched_preferred_companies.join(', ')}
                </span>
              )}
            </div>
          </div>
        </TableCell>
        <TableCell className="align-middle">
          <div className="flex justify-center">
            <CircularProgress percentage={Number(finalScore)} />
          </div>
        </TableCell>
        <TableCell className="text-center align-middle">
          {entry.explanation && (
            <button
              onClick={() => setExpanded((e) => !e)}
              className="inline-flex items-center justify-center gap-1.5 text-sm font-medium text-orange-400 hover:text-orange-300 transition-colors px-3 py-2 rounded-lg hover:bg-orange-500/10 w-full"
            >
              {expanded ? 'Hide Details' : 'AI Analysis'}
              {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
          )}
        </TableCell>
      </TableRow>
      
      {/* Expanded row for AI assessment */}
      {/* Expanded row for AI assessment */}
      {expanded && entry.explanation && (
        <TableRow className="bg-zinc-900/40 hover:bg-zinc-900/40 border-t-0">
          <TableCell colSpan={4} className="p-0 border-b border-zinc-800">
            <div className="p-4 pl-20 animate-fade-in">
              <div className="flex flex-col gap-4 bg-zinc-950/80 rounded-lg p-5 border border-zinc-800/80 shadow-inner">
                
                {/* Header */}
                <div className="flex items-center justify-between border-b border-zinc-800/50 pb-3">
                  <div className="flex items-center gap-2">
                    <ShieldAlert size={16} className="text-orange-500" />
                    <h4 className="text-sm font-semibold text-zinc-100 tracking-wide">AI Assessment</h4>
                    {aiData?.recommendation && (
                      <span className={`ml-3 px-2 py-0.5 rounded text-xs font-bold ${
                        String(aiData.recommendation).toLowerCase().includes('strong hire') ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                        String(aiData.recommendation).toLowerCase().includes('interview') ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
                        'bg-zinc-700/50 text-zinc-400 border border-zinc-600'
                      }`}>
                        {aiData.recommendation}
                      </span>
                    )}
                  </div>
                </div>

                {/* Body */}
                <div className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">
                  <p className="mb-2 max-w-5xl">{aiText}</p>
                  
                  {aiData && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-6 pt-6 border-t border-zinc-800/50">
                      {/* Left Column: Strengths */}
                      <div className="lg:col-span-1">
                        {Array.isArray(aiData.key_strengths) && aiData.key_strengths.length > 0 && (
                          <div>
                            <h5 className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-3">Key Strengths</h5>
                            <ul className="space-y-2">
                              {aiData.key_strengths.map((s: string, i: number) => (
                                <li key={i} className="flex items-start gap-2.5 text-sm text-zinc-300">
                                  <span className="w-1.5 h-1.5 rounded-full bg-orange-500/60 mt-1.5 shrink-0" />
                                  <span>{s}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                      
                      {/* Right Column: Skills & Culture */}
                      <div className="lg:col-span-2 flex flex-col gap-6">
                        {aiData.skills_scorecard && typeof aiData.skills_scorecard === 'object' && !Array.isArray(aiData.skills_scorecard) && Object.keys(aiData.skills_scorecard).length > 0 && (
                          <div>
                            <h5 className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-3">AI Skills Match</h5>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(aiData.skills_scorecard).map(([skill, score]: [string, any], i) => (
                                <span key={i} className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium border ${String(score).toLowerCase() === 'missing' ? 'bg-zinc-900/50 text-zinc-600 border-zinc-800/50' : 'bg-zinc-800 text-zinc-300 border-zinc-700'}`}>
                                  {skill}
                                  {String(score).toLowerCase() !== 'missing' && <span className="ml-1.5 pl-1.5 border-l border-zinc-700 text-orange-400/90">{String(score)}</span>}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        {aiData.culture_fit && (
                          <div>
                            <h5 className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-3">Culture & Soft Skills</h5>
                            <p className="text-sm text-zinc-400 max-w-3xl">{aiData.culture_fit}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
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
      <div className="mb-4 flex items-center justify-between px-1">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">
            Top {ranked.length} Candidates for{' '}
            <span className="text-orange-400">{positionTitle}</span>
          </h2>
          <span className="text-xs text-zinc-500">
            {result.total_candidates} evaluated · computed{' '}
            {result.computed_at ? new Date(result.computed_at).toLocaleTimeString() : '—'}
          </span>
        </div>
      </div>

      {ranked.length === 0 && (
        <p className="text-zinc-500 text-sm glass-panel p-6 text-center rounded-xl">
          No ranked results. Make sure candidates are embedded before running matching.
        </p>
      )}

      {/* Ranked Table */}
      {ranked.length > 0 && (
        <Table>
          <TableHeader className="border-zinc-800/50">
            <tr>
              <TableHead className="w-20 text-center font-semibold tracking-wider">Rank</TableHead>
              <TableHead className="font-semibold tracking-wider">Candidate</TableHead>
              <TableHead className="text-center font-semibold tracking-wider">Match Score</TableHead>
              <TableHead className="text-center font-semibold tracking-wider">Analysis</TableHead>
            </tr>
          </TableHeader>
          <TableBody>
            {ranked.map((entry, idx) => (
              <MatchRow key={entry.candidate_id} entry={entry} index={idx} />
            ))}
          </TableBody>
        </Table>
      )}

      {/* Filtered section */}
      <FilteredSection entries={filtered} />
    </div>
  )
}
