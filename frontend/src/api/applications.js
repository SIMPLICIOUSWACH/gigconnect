import api from './client'

export const applyToGig = (gigId, payload) =>
  api.post(`/gigs/${gigId}/applications/`, payload).then((r) => r.data)

export const fetchMyApplications = (params) => api.get('/applications/mine/', { params }).then((r) => r.data)

export const fetchGigApplicants = (gigId, params) =>
  api.get(`/gigs/${gigId}/applications/`, { params }).then((r) => r.data)

export const updateApplicationStatus = (id, status, note) =>
  api.patch(`/applications/${id}/status/`, note ? { status, note } : { status }).then((r) => r.data)

export const fetchApplication = (id) => api.get(`/applications/${id}/`).then((r) => r.data)

export const withdrawApplication = (id, reason) =>
  api.post(`/applications/${id}/withdraw/`, reason ? { reason } : {}).then((r) => r.data)
