import api from './client'

export const toFormData = (fields) => {
  const formData = new FormData()
  Object.entries(fields).forEach(([key, value]) => {
    if (value === undefined || value === null) return
    if (Array.isArray(value)) {
      value.forEach((item) => formData.append(key, item))
    } else {
      formData.append(key, value)
    }
  })
  return formData
}

export const completeProfile = (fields) =>
  api.patch('/profile/complete/', toFormData(fields), {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then((r) => r.data)

export const listPortfolioItems = () => api.get('/profile/portfolio-items/').then((r) => r.data)

export const createPortfolioItem = (fields) =>
  api.post('/profile/portfolio-items/', toFormData(fields), {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then((r) => r.data)

export const updatePortfolioItem = (id, fields) =>
  api.patch(`/profile/portfolio-items/${id}/`, toFormData(fields), {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then((r) => r.data)

export const deletePortfolioItem = (id) => api.delete(`/profile/portfolio-items/${id}/`)

export const submitVerification = (idNumber, idDocument) =>
  api.post('/profile/submit-verification/', toFormData({ id_number: idNumber, id_document: idDocument }), {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then((r) => r.data)

// A fresh random gesture for the selfie, with the consent wording. Single use, valid ten minutes.
export const fetchSelfieChallenge = () => api.get('/profile/verification/challenge/').then((r) => r.data)

export const submitSelfie = ({ selfie, challengeId, consent }) => {
  const body = new FormData()
  body.append('selfie', selfie, 'selfie.jpg')
  body.append('challenge_id', challengeId)
  body.append('consent', consent ? 'true' : 'false')
  return api
    .post('/profile/verification/selfie/', body, { headers: { 'Content-Type': 'multipart/form-data' } })
    .then((r) => r.data)
}

export const fetchPrivacyInfo = () => api.get('/meta/privacy/').then((r) => r.data)

export const fetchPublicProfile = (userId) => api.get(`/profiles/${userId}/`).then((r) => r.data)

// A JSON update of the freelancer profile. Unlike the form above it can send an empty skills list.
export const updateFreelancerProfile = (fields) => api.patch('/profile/complete/', fields).then((r) => r.data)
