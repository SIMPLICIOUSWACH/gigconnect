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

export const fetchPublicProfile = (userId) => api.get(`/profiles/${userId}/`).then((r) => r.data)
