import api from '../api/client'

const get = (url, params) => api.get(`/admin/${url}`, { params }).then((r) => r.data)
const post = (url, body) => api.post(`/admin/${url}`, body).then((r) => r.data)

// Leaves out empty filters, so the URL only carries the ones in use.
export const cleanParams = (params) =>
  Object.fromEntries(Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined))

export const fetchStats = () => get('stats/')
export const fetchRecommender = () => get('recommender/')

export const fetchUsers = (params) => get('users/', cleanParams(params))
export const fetchUser = (id) => get(`users/${id}/`)
export const suspendUser = (id, reason) => post(`users/${id}/suspend/`, { reason })
export const reinstateUser = (id, reason) => post(`users/${id}/reinstate/`, { reason })

export const fetchVerifications = (params) => get('verifications/', cleanParams(params))
export const decideVerification = (id, verificationStatus, reason = '') =>
  api.patch(`/admin/verifications/${id}/`, { verification_status: verificationStatus, reason }).then((r) => r.data)
// The ID document needs the admin's token, so it is fetched as a file rather than linked to.
export const fetchVerificationDocument = (id) =>
  api.get(`/admin/verifications/${id}/document/`, { responseType: 'blob' }).then((r) => r.data)

export const fetchGigs = (params) => get('gigs/', cleanParams(params))
export const fetchGig = (id) => get(`gigs/${id}/`)
export const removeGig = (id, reason) => post(`gigs/${id}/remove/`, { reason })
export const restoreGig = (id, reason) => post(`gigs/${id}/restore/`, { reason })

export const fetchApplications = (params) => get('applications/', cleanParams(params))
export const removeApplication = (id, reason) => post(`applications/${id}/remove/`, { reason })
export const restoreApplication = (id, reason) => post(`applications/${id}/restore/`, { reason })

export const fetchAuditLog = (params) => get('audit-log/', cleanParams(params))

export const fetchCategories = () => api.get('/categories/').then((r) => r.data)

// The message to show for a failed admin call: the server's own words when it gave any.
export function errorMessage(error, fallback = 'Something went wrong. Try again.') {
  const data = error?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (data && typeof data === 'object') {
    const first = Object.values(data).flat().find((value) => typeof value === 'string')
    if (first) return first
  }
  return fallback
}
