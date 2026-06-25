import axios from 'axios'

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

export default api
