import api from './client'

export const updateAccount = (fields) => api.patch('/settings/account/', fields).then((r) => r.data)

export const changePassword = (currentPassword, newPassword) =>
  api.post('/settings/change-password/', {
    current_password: currentPassword,
    new_password: newPassword,
  }).then((r) => r.data)

export const listSessions = () => api.get('/settings/sessions/').then((r) => r.data)

export const revokeSession = (id) => api.delete(`/settings/sessions/${id}/`)

export const logoutAllSessions = () => api.post('/settings/sessions/logout-all/').then((r) => r.data)

export const fetchNotificationPreferences = () => api.get('/settings/notifications/').then((r) => r.data)

export const updateNotificationPreferences = (fields) =>
  api.patch('/settings/notifications/', fields).then((r) => r.data)

export const exportData = () => api.get('/settings/export-data/').then((r) => r.data)

export const deleteAccount = (password) => api.post('/settings/delete-account/', { password }).then((r) => r.data)
