import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../../lib/api'

// ── Types ──────────────────────────────────────────────────────────────────────

export interface ScoreBreakdown {
  rule_score: number | null
  vector_score: number | null
  llm_score: number | null
  final_score: number | null
  rule_weight: number
  vector_weight: number
  llm_weight: number
  summary: string
}

export interface MatchEntry {
  rank: number | null
  candidate_id: string
  candidate_name: string | null
  is_filtered: boolean
  filter_reason: string | null
  rule_score: number | null
  vector_score: number | null
  llm_score: number | null
  final_score: number | null
  explanation: string | null
  source_name: string | null
  score_breakdown: ScoreBreakdown | null
}

export interface MatchResponse {
  job_id: string
  total_candidates: number
  passed_filter: number
  matches: MatchEntry[]
  computed_at: string | null
}

export interface RecomputeRequest {
  job_id: string
  source_filter?: string[] | null
  top_k?: number | null
}

// ── Hooks ──────────────────────────────────────────────────────────────────────

export function useMatches(
  positionId: string,
  topK?: number,
  sourceFilter?: string[],
  enabled = false,
) {
  const params: Record<string, string> = {}
  if (topK) params.top_k = String(topK)
  if (sourceFilter && sourceFilter.length > 0) params.source_filter = sourceFilter.join(',')

  return useQuery<MatchResponse>({
    queryKey: ['matches', positionId, topK, sourceFilter],
    queryFn: async () => {
      const { data } = await api.get<MatchResponse>(`/matches/${positionId}`, { params })
      return data
    },
    enabled: !!positionId && enabled,
    staleTime: 0,
  })
}

export function useRecompute() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: RecomputeRequest) => {
      const { data } = await api.post('/recompute-match', body)
      return data
    },
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ['matches', vars.job_id] })
    },
  })
}
