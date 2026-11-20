// Small date helpers for the chat. Times use the viewer's clock.

const sameDay = (a, b) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()

export function timeOf(iso) {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

export function dayOf(iso, now = new Date()) {
  const date = new Date(iso)
  if (sameDay(date, now)) return 'Today'
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (sameDay(date, yesterday)) return 'Yesterday'
  const options = { weekday: 'short', day: 'numeric', month: 'short' }
  if (date.getFullYear() !== now.getFullYear()) options.year = 'numeric'
  return date.toLocaleDateString('en-GB', options)
}

// For the conversation list: the time today, otherwise the date.
export function shortWhen(iso, now = new Date()) {
  if (!iso) return ''
  const date = new Date(iso)
  if (sameDay(date, now)) return timeOf(iso)
  const options = { day: 'numeric', month: 'short' }
  if (date.getFullYear() !== now.getFullYear()) options.year = 'numeric'
  return date.toLocaleDateString('en-GB', options)
}

export function longDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}
