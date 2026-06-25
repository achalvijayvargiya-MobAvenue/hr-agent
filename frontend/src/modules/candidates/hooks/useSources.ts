import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../../lib/api'

// ── Types ──────────────────────────────────────────────────────────────────────

export interface Source {
  name: string
  display_name: string
  is_available: boolean
}

export interface EducationEntry {
  degree: string | null
  institution: string | null
  year: number | null
}

export interface EmploymentEntry {
  title: string | null
  company: string | null
  start_date: string | null
  end_date: string | null
}

export interface Candidate {
  email: string
  name: string | null
  current_title: string | null
  normalized_role: string | null
  years_experience: number | null
  current_company: string | null
  location: string | null
  skills: string[]
  tools_and_technologies: string[]
  education: EducationEntry[]
  certifications: string[]
  employment_history: EmploymentEntry[]
  industries: string[]
  experience_areas: string[]
  responsibilities: string[]
  seniority_level: string | null
  summary: string | null
  source_name: string
  status: string
  created_at: string
}

export interface CandidateImport {
  import_id: string
  status: string
  source_name: string
  proposed_email: string | null
  existing_email: string | null
  name: string | null
  location: string | null
  extracted_data: Record<string, unknown> | null
  error_message: string | null
  created_at: string
}

export interface CandidateConflictExisting {
  email: string
  name: string | null
  current_title: string | null
  current_company: string | null
  location: string | null
  source_name: string
  summary: string | null
}

export interface CandidateConflict {
  import_id: string
  proposed_email: string
  source_name: string
  proposed: Record<string, unknown>
  existing: CandidateConflictExisting
}

export interface FetchResult {
  position_id: string
  sources_queried: string[]
  total_records: number
  new_candidates: number
}

// ── Hooks ──────────────────────────────────────────────────────────────────────

export function useSources() {
  return useQuery<Source[]>({
    queryKey: ['sources'],
    queryFn: async () => {
      const { data } = await api.get<Source[]>('/sources')
      return data
    },
  })
}

export function useFetchCandidates() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (positionId: string) => {
      const { data } = await api.post<FetchResult>(`/sources/fetch/${positionId}`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['candidates'] })
      queryClient.invalidateQueries({ queryKey: ['candidate-conflicts'] })
    },
  })
}

export function useCandidates(sourceName?: string) {
  return useQuery<Candidate[]>({
    queryKey: ['candidates', sourceName],
    queryFn: async () => {
      const params = sourceName ? { source_name: sourceName } : {}
      const { data } = await api.get<Candidate[]>('/candidates', { params })
      return data
    },
  })
}

export function useCandidate(email: string) {
  return useQuery<Candidate>({
    queryKey: ['candidate', email],
    queryFn: async () => {
      const { data } = await api.get<Candidate>(`/candidates/${encodeURIComponent(email)}`)
      return data
    },
    enabled: !!email,
  })
}

export function useCandidateImports() {
  return useQuery<CandidateImport[]>({
    queryKey: ['candidate-imports'],
    queryFn: async () => {
      const { data } = await api.get<CandidateImport[]>('/candidates/imports')
      return data
    },
    refetchInterval: 5000,
  })
}

export function useCandidateConflicts() {
  return useQuery<CandidateConflict[]>({
    queryKey: ['candidate-conflicts'],
    queryFn: async () => {
      const { data } = await api.get<CandidateConflict[]>('/candidates/imports/conflicts')
      return data
    },
    refetchInterval: 5000,
  })
}

export function useResolveConflict() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ importId, action }: { importId: string; action: 'update' | 'keep' }) => {
      const { data } = await api.post(`/candidates/imports/${importId}/resolve`, { action })
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['candidates'] })
      queryClient.invalidateQueries({ queryKey: ['candidate-conflicts'] })
      queryClient.invalidateQueries({ queryKey: ['candidate-imports'] })
    },
  })
}

export function useDismissImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (importId: string) => {
      await api.delete(`/candidates/imports/${importId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['candidate-imports'] })
      queryClient.invalidateQueries({ queryKey: ['candidate-conflicts'] })
    },
  })
}

export function useDeleteCandidate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (email: string) => {
      await api.delete(`/candidates/${encodeURIComponent(email)}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['candidates'] })
    },
  })
}
