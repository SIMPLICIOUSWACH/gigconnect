import { Link, useLocation } from 'react-router-dom'
import { logSearchClick } from '../../api/gigs'
import { formatBudget, formatDate, formatRelativeTime, isApplicationClosed, isUrgent } from '../../utils/gigFormat'

const STATUS_LABELS = {
  in_progress: 'In Progress',
  completed: 'Completed',
  closed: 'Closed',
}

function locationLabel(gig) {
  if (gig.is_remote && gig.county) return `${gig.county} or remote`
  if (gig.is_remote) return 'Remote'
  return gig.county || ''
}

export default function GigCard({ gig, position, query }) {
  const location = useLocation()
  const urgent = isUrgent(gig.application_deadline)
  // Only reachable via the "Show closed gigs" toggle — the default feed never returns these.
  const statusBadge = gig.status !== 'open' ? STATUS_LABELS[gig.status] : null
  const applicationsClosed = !statusBadge && isApplicationClosed(gig.application_deadline)
  const visibleSkills = gig.skills.slice(0, 4)
  const extraCount = gig.skills.length - visibleSkills.length

  return (
    <div className="bg-surface rounded-xl border border-border p-6 hover:border-primary/40 transition-colors flex flex-col">
      <div className="flex items-start justify-between gap-3 mb-2">
        <Link
          to={`/gigs/${gig.id}`}
          state={{ from: `${location.pathname}${location.search}` }}
          onClick={() => logSearchClick(gig.id, { query, position })}
          className="text-section-title text-ink hover:text-primary"
        >
          {gig.title}
        </Link>
        {urgent && (
          <span className="text-caption font-medium px-2.5 py-1 rounded-full bg-red-50 text-red-700 shrink-0">
            Urgent
          </span>
        )}
        {(statusBadge || applicationsClosed) && (
          <span className="text-caption font-medium px-2.5 py-1 rounded-full bg-bg text-muted shrink-0">
            {statusBadge || 'Applications closed'}
          </span>
        )}
      </div>

      <p className="text-body text-muted mb-3">
        {gig.client_name} · {gig.category.name}
        {locationLabel(gig) && ` · ${locationLabel(gig)}`}
      </p>

      <div className="flex flex-wrap gap-2 mb-4">
        {visibleSkills.map((skill) => (
          <span
            key={skill.id}
            className="text-caption font-medium px-2.5 py-1 rounded-full bg-primary-light text-primary"
          >
            {skill.name}
          </span>
        ))}
        {extraCount > 0 && (
          <span className="text-caption font-medium px-2.5 py-1 rounded-full bg-bg text-muted">
            +{extraCount} more
          </span>
        )}
      </div>

      <div className="flex items-end justify-between gap-4 pt-4 mt-auto border-t border-border">
        <div>
          <p className="text-section-title text-primary">{formatBudget(gig)}</p>
          {gig.is_negotiable && <p className="text-caption text-muted mt-0.5">Negotiable</p>}
        </div>
        <div className="text-right">
          <p className="text-caption text-muted">Deadline {formatDate(gig.deadline)}</p>
          <p className="text-caption text-muted mt-0.5">Posted {formatRelativeTime(gig.created_at)}</p>
        </div>
      </div>
    </div>
  )
}
