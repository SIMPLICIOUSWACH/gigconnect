import api, { tokenStorage } from './client'

export const register = (payload) => api.post('/auth/register/', payload).then((r) => r.data)

export const login = async (email, password) => {
  const { data } = await api.post('/auth/login/', { email, password })
  tokenStorage.set(data.access, data.refresh)
  return data
}

export const logout = () => {
  tokenStorage.clear()
}

export const fetchMe = () => api.get('/auth/me/').then((r) => r.data)

export const verifyEmail = (token) => api.get(`/auth/verify-email/${token}/`).then((r) => r.data)

export const sendOtp = () => api.post('/auth/send-otp/').then((r) => r.data)

export const verifyOtp = (code) => api.post('/auth/verify-otp/', { code }).then((r) => r.data)

export const fetchSkills = () => api.get('/skills/').then((r) => r.data)
