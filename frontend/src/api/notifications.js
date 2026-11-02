import api from './client'

export const fetchNotifications = (params) => api.get('/notifications/', { params }).then((r) => r.data)

export const fetchUnreadCount = () => api.get('/notifications/unread-count/').then((r) => r.data.unread)

export const markNotificationRead = (id) => api.post(`/notifications/${id}/read/`).then((r) => r.data)

export const markAllNotificationsRead = () => api.post('/notifications/read-all/').then((r) => r.data)

// Lets the bell update at once when the notifications page marks something as read.
const CHANGED = 'gigconnect:notifications-changed'
export const announceNotificationsChanged = () => window.dispatchEvent(new Event(CHANGED))
export const onNotificationsChanged = (handler) => {
  window.addEventListener(CHANGED, handler)
  return () => window.removeEventListener(CHANGED, handler)
}
