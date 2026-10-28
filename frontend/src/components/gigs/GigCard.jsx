import { Link, useLocation } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { logSearchClick } from '../../api/gigs'
import { formatBudget, formatShortDate, isApplicationClosed, isUrgent } from '../../utils/gigFormat'
import { categoryColour, initials } from '../../utils/palette'

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

// onOpen replaces the default search-click logging, for lists that are not search results (the
// recommendations). It is called with the gig and its position in the list.
export default function GigCard({ gig, position, query, onOpen }) {
  const location = useLocation()
  const urgent = isUrgent(gig.application_deadline)
  // Only reachable via the "Show closed gigs" toggle — the default feed never returns these.
  const statusBadge = gig.status !== 'open' ? STATUS_LABELS[gig.status] : null
  const applicationsClosed = !statusBadge && isApplicationClosed(gig.application_deadline)
  const visibleSkills = gig.skills.slice(0, 4)
  const extraCount = gig.skills.length - visibleSkills.length
  const colour = categoryColour(gig.category.slug || gig.category.name)
  const where = locationLabel(gig)

  const linkProps = {
    to: `/gigs/${gig.id}`,
    state: { from: `${location.pathname}${location.search}` },
    onClick: () => (onOpen ? onOpen(gig, position) : logSearchClick(gig.id, { query, position })),
  }

  return (
    <article className="bg-surface rounded-card p-[22px] flex flex-col gap-3.5 shadow-hairline">
      <div className="flex flex-wrap gap-1.5">
        <span className={`text-badge px-[11px] py-[5px] rounded-pill ${colour}`}>{gig.category.name}</span>
        {urgent && !statusBadge && (
          <span className="text-badge px-[11px] py-[5px] rounded-pill bg-coral-deep text-white">Urgent</span>
        )}
        {(statusBadge || applicationsClosed) && (
          <span className="text-badge px-[11px] py-[5px] rounded-pill bg-sand text-ink-soft">
            {statusBadge || 'Applications closed'}
          </span>
        )}
      </div>

      <h3 className="font-display text-card-title">
        <Link {...linkProps} className="text-ink hover:text-primary">
          {gig.title}
        </Link>
      </h3>

      <div className="flex flex-wrap items-center gap-2.5">
        <span
          aria-hidden="true"
          className={`w-[34px] h-[34px] rounded-full flex items-center justify-center font-bold text-[12px] ${colour}`}
        >
          {initials(gig.client_name)}
        </span>
        <span className="text-[14px] font-medium">{gig.client_name}</span>
        {where && <span className="text-caption text-muted">· {where}</span>}
      </div>

      {visibleSkills.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {visibleSkills.map((skill) => (
            <span key={skill.id} className="text-caption text-ink-soft bg-sand px-[11px] py-[5px] rounded-pill">
              {skill.name}
            </span>
          ))}
          {extraCount > 0 && (
            <span className="text-caption text-muted bg-sand px-[11px] py-[5px] rounded-pill">+{extraCount} more</span>
          )}
        </div>
      )}

      <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-3.5 border-t border-dashed border-divider">
        <div className="flex flex-col gap-0.5">
          <span className="font-display text-[22px] font-extrabold tracking-[-0.01em] tabular-nums">
            {formatBudget(gig)}
          </span>
          <span className="text-caption text-muted">
            {gig.is_negotiable ? 'Negotiable' : 'Fixed price'}
            {gig.application_deadline && ` · Apply by ${formatShortDate(gig.application_deadline)}`}
          </span>
        </div>
        <Link
          {...linkProps}
          aria-label={`Apply: ${gig.title}`}
          className="inline-flex items-center gap-2 min-h-[46px] px-5 rounded-button bg-coral text-ink text-[15px] font-bold hover:bg-coral/90"
        >
          Apply
          <ArrowRight size={16} strokeWidth={2.2} aria-hidden="true" />
        </Link>
      </div>
    </article>
  )
}
