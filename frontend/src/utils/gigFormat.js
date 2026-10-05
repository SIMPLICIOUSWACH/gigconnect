export function formatBudget(gig) {
  const min = Number(gig.budget_min)
  const max = Number(gig.budget_max)
  const fmt = (n) => n.toLocaleString('en-US')
  if (min === max) return `${gig.currency} ${fmt(min)}`
  return `${gig.currency} ${fmt(min)} – ${fmt(max)}`
}

export function formatDate(isoDateString) {
  if (!isoDateString) return ''
  return new Date(`${isoDateString}T00:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function isUrgent(applicationDeadline) {
  if (!applicationDeadline) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const deadline = new Date(`${applicationDeadline}T00:00:00`)
  const diffDays = Math.round((deadline - today) / 86400000)
  return diffDays >= 0 && diffDays <= 3
}

export function isApplicationClosed(applicationDeadline) {
  if (!applicationDeadline) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return new Date(`${applicationDeadline}T00:00:00`) < today
}

export function formatRelativeTime(isoDateTimeString) {
  const then = new Date(isoDateTimeString)
  const diffMs = Date.now() - then.getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`
  const months = Math.floor(days / 30)
  if (months < 12) return `${months} month${months === 1 ? '' : 's'} ago`
  const years = Math.floor(months / 12)
  return `${years} year${years === 1 ? '' : 's'} ago`
}
