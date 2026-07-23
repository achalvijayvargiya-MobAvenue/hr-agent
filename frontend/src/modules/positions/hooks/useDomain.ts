import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../../lib/api'

export interface TaxonomySubdomain {
  code: string
  label: string
  adjacent: string[]
}

export interface TaxonomyDomain {
  code: string
  label: string
  description: string
  subdomains: TaxonomySubdomain[]
}

export interface Taxonomy {
  version: string
  domains: TaxonomyDomain[]
}

export function useTaxonomy() {
  return useQuery<Taxonomy>({
    queryKey: ['taxonomy'],
    queryFn: async () => {
      const { data } = await api.get<Taxonomy>('/taxonomy')
      return data
    },
    staleTime: 1000 * 60 * 60,
  })
}

export interface DomainUpdateBody {
  domain_code: string
  subdomain_codes: string[]
}

export function useClassifyJobDomain() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (jobId: string) => {
      const { data } = await api.post(`/jobs/${jobId}/classify-domain`)
      return data
    },
    onSuccess: (_data, jobId) => {
      queryClient.invalidateQueries({ queryKey: ['position', jobId] })
      queryClient.invalidateQueries({ queryKey: ['job-pool', jobId] })
    },
  })
}

export function useUpdateJobDomain() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ jobId, body }: { jobId: string; body: DomainUpdateBody }) => {
      const { data } = await api.put(`/jobs/${jobId}/domain`, body)
      return data
    },
    onSuccess: (_data, { jobId }) => {
      queryClient.invalidateQueries({ queryKey: ['position', jobId] })
      queryClient.invalidateQueries({ queryKey: ['job-pool', jobId] })
    },
  })
}

export interface PoolEntry {
  candidate_id: string
  candidate_name: string | null
  current_title: string | null
  domain_code: string | null
  subdomain_codes: string[]
  pool_status: 'in_pool' | 'out_of_pool' | 'manual_add' | 'manual_exclude'
  domain_match_score: number
  subdomain_match_score: number
  relevance_score: number
  match_reason: string | null
  computed_at: string
  application_status: string | null
}

export interface PoolResult {
  job_id: string
  total_candidates: number
  in_pool: number
  out_of_pool: number
  manual_add: number
  manual_exclude: number
  computed_at: string
  entries: PoolEntry[]
}

export function useJobPool(jobId: string, enabled = true) {
  return useQuery<PoolResult>({
    queryKey: ['job-pool', jobId],
    queryFn: async () => {
      const { data } = await api.get<PoolResult>(`/jobs/${jobId}/pool`)
      return data
    },
    enabled: !!jobId && enabled,
  })
}

export function useBuildJobPool() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (jobId: string) => {
      const { data } = await api.post<PoolResult>(`/jobs/${jobId}/pool/build`)
      return data
    },
    onSuccess: (_data, jobId) => {
      queryClient.invalidateQueries({ queryKey: ['job-pool', jobId] })
    },
  })
}

export function useUpdatePoolMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      jobId,
      candidateId,
      pool_status,
    }: {
      jobId: string
      candidateId: string
      pool_status: 'manual_add' | 'manual_exclude' | 'auto'
    }) => {
      const { data } = await api.put(`/jobs/${jobId}/pool/${encodeURIComponent(candidateId)}`, {
        pool_status,
      })
      return data
    },
    onSuccess: (_data, { jobId }) => {
      queryClient.invalidateQueries({ queryKey: ['job-pool', jobId] })
    },
  })
}
