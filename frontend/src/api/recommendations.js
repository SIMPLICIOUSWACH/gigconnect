import api from './client'

export const fetchRecommendations = (params) => api.get('/recommendations/', { params }).then((r) => r.data)
