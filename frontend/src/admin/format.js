// Wording and formatting shared by the admin pages.

const DATE = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
const DATE_TIME = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export const formatDate = (value) => (value ? DATE.format(new Date(value)) : '')
export const formatDateTime = (value) => (value ? DATE_TIME.format(new Date(value)) : '')
export const formatNumber = (value) => (value ?? 0).toLocaleString('en-GB')

export const formatBudget = (gig) =>
  `KES ${Number(gig.budget_min).toLocaleString('en-GB')} – ${Number(gig.budget_max).toLocaleString('en-GB')}`

export const ROLE_LABELS = { client: 'Client', freelancer: 'Freelancer', admin: 'Admin' }

export const ACCOUNT_STATUS = {
  active: { label: 'Active', tone: 'mint' },
  suspended: { label: 'Suspended', tone: 'coral' },
  deleted: { label: 'Deleted', tone: 'sand' },
}

export const VERIFICATION = {
  verified: { label: 'ID verified', tone: 'mint' },
  pending: { label: 'ID pending', tone: 'sun' },
  rejected: { label: 'ID rejected', tone: 'coral' },
  unverified: { label: 'Not verified', tone: 'sand' },
}

export const GIG_STATUS = {
  open: 'Open',
  in_progress: 'In progress',
  completed: 'Completed',
  closed: 'Closed',
}

export const APPLICATION_STATUS = {
  pending: 'Pending',
  under_review: 'Under review',
  shortlisted: 'Shortlisted',
  hired: 'Hired',
  rejected: 'Rejected',
  withdrawn: 'Withdrawn',
}

export const ACTION_LABELS = {
  verify_approve: 'Approved ID',
  verify_reject: 'Rejected ID',
  suspend_user: 'Suspended user',
  reinstate_user: 'Reinstated user',
  remove_gig: 'Removed gig',
  restore_gig: 'Restored gig',
  remove_application: 'Removed application',
  restore_application: 'Restored application',
}

export const NEGATIVE_ACTIONS = new Set(['verify_reject', 'suspend_user', 'remove_gig', 'remove_application'])

// Where an audit log row's target opens in the admin area.
export function targetPath(row) {
  if (row.target_type === 'user') return `/admin/users/${row.target_id}`
  if (row.target_type === 'gig') return `/admin/gigs/${row.target_id}`
  return `/admin/applications?id=${row.target_id}`
}

export const TARGET_TYPE_LABELS = { user: 'User', gig: 'Gig', application: 'Application' }
