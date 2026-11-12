import api from './client'

export const MESSAGE_MAX_LENGTH = 2000

export const fetchConversations = (params) => api.get('/conversations/', { params }).then((r) => r.data)

export const fetchConversation = (id) => api.get(`/conversations/${id}/`).then((r) => r.data)

export const fetchMessageUnreadCount = () => api.get('/conversations/unread-count/').then((r) => r.data.unread)

// {results, has_earlier, seen_up_to}. Pass {after: id} to poll for newer messages, {before: id} for earlier ones.
export const fetchMessages = (id, params) => api.get(`/conversations/${id}/messages/`, { params }).then((r) => r.data)

export const sendMessage = (id, body) => api.post(`/conversations/${id}/messages/`, { body }).then((r) => r.data)

export const markConversationRead = (id) => api.post(`/conversations/${id}/read/`).then((r) => r.data)

export const reportConversation = (id, reason) =>
  api.post(`/conversations/${id}/report/`, { reason }).then((r) => r.data)

// Lets the navbar badge update at once when a chat is read.
const CHANGED = 'gigconnect:messages-changed'
export const announceMessagesChanged = () => window.dispatchEvent(new Event(CHANGED))
export const onMessagesChanged = (handler) => {
  window.addEventListener(CHANGED, handler)
  return () => window.removeEventListener(CHANGED, handler)
}
