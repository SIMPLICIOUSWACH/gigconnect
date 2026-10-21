// One place for how an application status is named and coloured. Which moves are allowed is
// decided by the backend (allowed_next_statuses), never worked out here.
export const STATUS_INFO = {
  pending: { label: 'Pending', className: 'bg-amber-50 text-amber-800' },
  under_review: { label: 'Under review', className: 'bg-primary-light text-primary' },
  shortlisted: { label: 'Shortlisted', className: 'bg-primary-light text-primary' },
  hired: { label: 'Hired', className: 'bg-accent-light text-accent' },
  rejected: { label: 'Not selected', className: 'bg-red-50 text-red-700' },
  withdrawn: { label: 'Withdrawn', className: 'bg-bg text-muted' },
}

// What a client's button says for each move. Which moves are offered comes from the server.
export const ACTION_LABELS = {
  under_review: 'Start review',
  shortlisted: 'Shortlist',
  hired: 'Hire',
  rejected: 'Reject',
}

// Moves that are hard to undo ask for confirmation first (and take an optional note).
export const CONFIRMED_ACTIONS = ['hired', 'rejected']

export function statusLabel(status) {
  return STATUS_INFO[status]?.label ?? status
}

export function formatDateTime(isoDateTimeString) {
  if (!isoDateTimeString) return ''
  return new Date(isoDateTimeString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}
