import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../../lib/api'

// ── Types ──────────────────────────────────────────────────────────────────────

export interface ScoreBreakdown {
  rule_score: number | null
  vector_score: number | null
  rerank_score?: number | null
  llm_score: number | null
  final_score: number | null
  requirement_fit_score?: number | null
  rule_weight: number
  vector_weight: number
  rerank_weight?: number | null
  requirement_fit_weight?: number | null
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
  rerank_score?: number | null
  llm_score: number | null
  final_score: number | null
  requirement_fit_score?: number | null
  requirement_gaps?: string[] | null
  explanation: string | null
  source_name: string | null
  application_status?: string | null
  switch_frequency?: number | null
  matched_preferred_companies?: string[]
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

export function useSyncStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (jobId: string) => {
      const { data } = await api.post(`/matches/${jobId}/sync-status`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['candidates'] })
      queryClient.invalidateQueries({ queryKey: ['matches'] })
    }
  })
}

export function useLiveMatches(positionId: string, enabled = false) {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!enabled || !positionId) return

    // Replace with your actual base URL or API URL base
    const eventSource = new EventSource(`${api.defaults.baseURL || '/api/v1'}/matches/${positionId}/live`, {
      withCredentials: true
    })

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        
        // Update the query cache directly for an instant update
        queryClient.setQueriesData<MatchResponse>(
          { queryKey: ['matches', positionId] },
          (oldData) => {
            if (!oldData) return oldData
            
            return {
              ...oldData,
              matches: oldData.matches.map(m => 
                m.candidate_id === payload.candidate_email 
                  ? { ...m, application_status: payload.status }
                  : m
              )
            }
          }
        )
      } catch (e) {
        console.error('Failed to parse SSE event', e)
      }
    }

    eventSource.onerror = (e) => {
      console.error('SSE connection error', e)
    }

    return () => {
      eventSource.close()
    }
  }, [positionId, enabled, queryClient])
}
