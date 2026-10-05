import api from './client'

export const fetchCounties = () => api.get('/meta/counties/').then((r) => r.data)
