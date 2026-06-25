import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../../lib/api'

export interface Position {
  id: string
  title: string | null
  normalized_role: string | null
  experience_min: number | null
  experience_max: number | null
  employment_type: string | null
  location: string | null
  department: string | null
  industry: string | null
  must_have_skills: string[]
  good_to_have_skills: string[]
  tools_and_technologies: string[]
  education_requirements: string[]
  certifications: string[]
  responsibilities: string[]
  seniority_level: string | null
  summary: string | null
  hard_checks: Record<string, unknown> | null
  candidates_required: number | null
  position_status: string
  created_by: string | null
  status: string
  created_at: string
}

export interface PositionUpdateBody {
  title?: string | null
  normalized_role?: string | null
  department?: string | null
  industry?: string | null
  location?: string | null
  employment_type?: string | null
  seniority_level?: string | null
  experience_min?: number | null
  experience_max?: number | null
  candidates_required?: number | null
  must_have_skills?: string[]
  good_to_have_skills?: string[]
  tools_and_technologies?: string[]
  education_requirements?: string[]
  certifications?: string[]
  responsibilities?: string[]
  summary?: string | null
  position_status?: string | null
}

export interface PositionApproveBody {
  title?: string | null
  normalized_role?: string | null
  department?: string | null
  industry?: string | null
  location?: string | null
  employment_type?: string | null
  seniority_level?: string | null
  experience_min?: number | null
  experience_max?: number | null
  candidates_required?: number | null
  must_have_skills?: string[]
  good_to_have_skills?: string[]
  tools_and_technologies?: string[]
  education_requirements?: string[]
  certifications?: string[]
  responsibilities?: string[]
  summary?: string | null
}

export interface ManualPositionBody {
  title: string
  normalized_role?: string | null
  department?: string | null
  industry?: string | null
  location?: string | null
  employment_type?: string | null
  seniority_level?: string | null
  experience_min?: number | null
  experience_max?: number | null
  candidates_required?: number | null
  must_have_skills?: string[]
  good_to_have_skills?: string[]
  tools_and_technologies?: string[]
  summary?: string | null
}

export function usePositions(status?: string) {
  return useQuery<Position[]>({
    queryKey: ['positions', status],
    queryFn: async () => {
      const params = status ? { status } : {}
      const { data } = await api.get<Position[]>('/jobs', { params })
      return data
    },
  })
}

export function usePosition(id: string) {
  return useQuery<Position>({
    queryKey: ['position', id],
    queryFn: async () => {
      const { data } = await api.get<Position>(`/jobs/${id}`)
      return data
    },
    enabled: !!id,
  })
}

export function useUploadPosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      const { data } = await api.post<{ job_id: string; status: string; message: string }>(
        '/jobs/upload',
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['positions'] })
    },
  })
}

export function useCreateManualPosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: ManualPositionBody) => {
      const { data } = await api.post<Position>('/jobs/manual', body)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['positions'] })
    },
  })
}

export function useApprovePosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: PositionApproveBody }) => {
      const { data } = await api.post<Position>(`/jobs/${id}/approve`, body)
      return data
    },
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['positions'] })
      queryClient.invalidateQueries({ queryKey: ['position', id] })
    },
  })
}

export function useUpdatePosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: PositionUpdateBody }) => {
      const { data } = await api.put<Position>(`/jobs/${id}`, body)
      return data
    },
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['positions'] })
      queryClient.invalidateQueries({ queryKey: ['position', id] })
    },
  })
}

export function useDeletePosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/jobs/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['positions'] })
    },
  })
}

export type HardChecks = Record<string, string | string[]>

export function useUpdateHardChecks() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, hard_checks }: { id: string; hard_checks: HardChecks }) => {
      const { data } = await api.put<Position>(`/jobs/${id}/hard-checks`, { hard_checks })
      return data
    },
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['positions'] })
      queryClient.invalidateQueries({ queryKey: ['position', id] })
    },
  })
}
