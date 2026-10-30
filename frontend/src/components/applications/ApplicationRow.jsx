import { Link } from 'react-router-dom'
import { formatDateTime } from '../../utils/applicationStatus'
import StatusBadge from './StatusBadge'

export default function ApplicationRow({ application }) {
  const removed = application.moderation_status === 'removed'
  return (
    <li className="bg-surface rounded-xl border border-border p-5 flex flex-wrap items-center justify-between gap-4">
      <div className="min-w-0">
        <Link
          to={`/gigs/${application.gig_id}`}
          className="block text-section-title text-primary hover:underline truncate"
        >
          {application.gig_title}
        </Link>
        <p className="text-body text-muted">
          {application.client_name} · Applied {formatDateTime(application.created_at)}
        </p>
        {removed && (
          <p className="text-body text-coral-ink mt-1">
            An administrator removed this application, so the client can no longer see it.
            {application.removed_reason && ` Reason: ${application.removed_reason}`}
          </p>
        )}
      </div>
      <div className="flex items-center gap-4">
        {removed ? (
          <span className="text-caption font-semibold px-2.5 py-1 rounded-pill bg-coral-light text-coral-ink">
            Removed
          </span>
        ) : (
          <StatusBadge status={application.status} />
        )}
        <Link to={`/applications/${application.id}`} className="text-body text-primary font-medium">
          View application
        </Link>
      </div>
    </li>
  )
}
