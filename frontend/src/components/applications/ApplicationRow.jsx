import { Link } from 'react-router-dom'
import { formatDateTime } from '../../utils/applicationStatus'
import StatusBadge from './StatusBadge'

export default function ApplicationRow({ application }) {
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
      </div>
      <div className="flex items-center gap-4">
        <StatusBadge status={application.status} />
        <Link to={`/applications/${application.id}`} className="text-body text-primary font-medium">
          View application
        </Link>
      </div>
    </li>
  )
}
