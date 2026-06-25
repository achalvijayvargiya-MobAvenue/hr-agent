import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../../lib/api'

// ── Types ──────────────────────────────────────────────────────────────────────

export interface AppUser {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  roles: string[]
  created_at: string
}

export interface Role {
  id: string
  name: string
  description: string | null
}

// ── Hooks ──────────────────────────────────────────────────────────────────────

export function useUsers() {
  return useQuery<AppUser[]>({
    queryKey: ['users'],
    queryFn: async () => {
      const { data } = await api.get<AppUser[]>('/users')
      return data
    },
  })
}

export function useRoles() {
  return useQuery<Role[]>({
    queryKey: ['roles'],
    queryFn: async () => {
      const { data } = await api.get<Role[]>('/roles')
      return data
    },
  })
}

export function useUpdateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: { full_name?: string | null; is_active?: boolean } }) => {
      const { data } = await api.put<AppUser>(`/users/${id}`, body)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })
}

export function useAssignRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ userId, roleName }: { userId: string; roleName: string }) => {
      const { data } = await api.post<AppUser>(`/users/${userId}/roles`, { role_name: roleName })
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })
}

export function useRemoveRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ userId, roleName }: { userId: string; roleName: string }) => {
      const { data } = await api.delete<AppUser>(`/users/${userId}/roles/${roleName}`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })
}

export function useInviteUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: { email: string; password: string; full_name?: string }) => {
      const { data } = await api.post<AppUser>('/auth/register', body)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })
}
