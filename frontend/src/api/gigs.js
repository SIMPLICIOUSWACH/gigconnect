import api from './client'

export const fetchCategories = () => api.get('/categories/').then((r) => r.data)

export const fetchGigsPaged = (params) => api.get('/gigs/', { params }).then((r) => r.data)

export const logSearchClick = (gigId, { query, position }) =>
  api.post(`/gigs/${gigId}/interactions/`, { type: 'search_click', query: query || null, position }).catch(() => {})

export const fetchGig = (id) => api.get(`/gigs/${id}/`).then((r) => r.data)

export const fetchMyGigs = () => api.get('/gigs/mine/').then((r) => r.data)

export const createGig = (payload) => api.post('/gigs/', payload).then((r) => r.data)

export const updateGig = (id, payload) => api.put(`/gigs/${id}/`, payload).then((r) => r.data)

export const deleteGig = (id) => api.delete(`/gigs/${id}/`)

export const updateGigStatus = (id, statusValue) =>
  api.patch(`/gigs/${id}/status/`, { status: statusValue }).then((r) => r.data)
