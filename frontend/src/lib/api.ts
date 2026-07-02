import axios from 'axios'
import { clearToken } from './auth'

const api = axios.create({
  baseURL:
    import.meta.env.VITE_API_BASE_URL ??
    (import.meta.env.DEV
      ? 'http://localhost:8000/api/v1'
      : 'https://hr-agent-api-n00g.onrender.com/api/v1'),
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('hr_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken()
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.replace('/login')
      }
    }
    return Promise.reject(error)
  }
)

export default api
