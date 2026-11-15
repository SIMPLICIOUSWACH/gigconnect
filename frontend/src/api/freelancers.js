import api from './client'

// Find freelancers, for clients and admins. 12 per page. See docs/api-endpoints.md for the filters.
export const searchFreelancers = (params) => api.get('/freelancers/', { params }).then((r) => r.data)

// Up to 6 freelancers the content model ranks best for one of the client's open gigs.
export const fetchSuggestedFreelancers = (gigId) =>
  api.get(`/gigs/${gigId}/suggested-freelancers/`).then((r) => r.data)

// The client's open gigs, each with whether this freelancer was already invited or has applied.
export const fetchInvitableGigs = (freelancerId) =>
  api.get(`/freelancers/${freelancerId}/invitable-gigs/`).then((r) => r.data)

// Sends the freelancer a notification with the gig link. One per freelancer per gig, 20 a day.
export const inviteToApply = (gigId, freelancerId) =>
  api.post(`/gigs/${gigId}/invites/`, { freelancer_id: freelancerId }).then((r) => r.data)

export const inviteError = (err, fallback = 'Could not send the invitation. Try again.') =>
  err?.response?.data?.detail || fallback
