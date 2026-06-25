import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import { clearToken, setToken } from '../../lib/auth'

export interface CurrentUser {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  roles: string[]
  created_at: string
}

export function useCurrentUser() {
  return useQuery<CurrentUser>({
    queryKey: ['currentUser'],
    queryFn: async () => {
      const { data } = await api.get<CurrentUser>('/auth/me')
      return data
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
  })
}

export function useLogin() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  return useMutation({
    mutationFn: async (credentials: { email: string; password: string }) => {
      const { data } = await api.post<{ access_token: string }>('/auth/login', credentials)
      return data
    },
    onSuccess: (data) => {
      setToken(data.access_token)
      queryClient.invalidateQueries({ queryKey: ['currentUser'] })
      navigate('/positions')
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  return () => {
    clearToken()
    queryClient.clear()
    navigate('/login')
  }
}
