import axios from 'axios'

const ACCESS_KEY = 'gc_access'
const REFRESH_KEY = 'gc_refresh'

export const tokenStorage = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access, refresh) => {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const access = tokenStorage.getAccess()
  if (access) config.headers.Authorization = `Bearer ${access}`
  return config
})

let onAuthFailure = () => {}
export const setOnAuthFailure = (handler) => {
  onAuthFailure = handler
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const isAuthEndpoint = original?.url?.includes('/auth/login') || original?.url?.includes('/auth/token/refresh')

    if (error.response?.status === 401 && !original._retry && !isAuthEndpoint && tokenStorage.getRefresh()) {
      original._retry = true
      try {
        const { data } = await axios.post('/api/auth/token/refresh/', {
          refresh: tokenStorage.getRefresh(),
        })
        tokenStorage.set(data.access, data.refresh)
        original.headers.Authorization = `Bearer ${data.access}`
        return api(original)
      } catch {
        tokenStorage.clear()
        onAuthFailure()
      }
    }

    return Promise.reject(error)
  }
)

export default api
