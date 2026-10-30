import api from './client'

export const fetchRecommendations = (params) => api.get('/recommendations/', { params }).then((r) => r.data)

/** Answer "Is this gig relevant to you?" for a recommended gig. A new answer replaces the old one. */
export const setRelevance = (gigId, relevant, position) =>
  api.put(`/recommendations/${gigId}/relevance/`, { relevant, position }).then((r) => r.data)
