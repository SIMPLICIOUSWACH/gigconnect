import api from './client'

export const REVIEW_MAX_LENGTH = 1000
export const REPLY_MAX_LENGTH = 500

// The client's own review of their gig. Rating and editing are open for 14 days after the gig is completed.
export const fetchGigReview = (gigId) => api.get(`/gigs/${gigId}/review/`).then((r) => r.data)
export const createReview = (gigId, body) => api.post(`/gigs/${gigId}/review/`, body).then((r) => r.data)
export const updateReview = (gigId, body) => api.patch(`/gigs/${gigId}/review/`, body).then((r) => r.data)

// The freelancer's one public reply.
export const replyToReview = (reviewId, reply) => api.post(`/reviews/${reviewId}/reply/`, { reply }).then((r) => r.data)

export const fetchFreelancerReviews = (userId, params) =>
  api.get(`/freelancers/${userId}/reviews/`, { params }).then((r) => r.data)

// The first thing the server said was wrong, in its own words.
export function reviewError(err, fallback) {
  const data = err?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  const first = data && Object.values(data).flat().find((value) => typeof value === 'string')
  return first || fallback
}
