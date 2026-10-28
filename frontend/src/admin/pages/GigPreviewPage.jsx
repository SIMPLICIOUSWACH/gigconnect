import { Link, useParams } from 'react-router-dom'
import { fetchGig, removeGig, restoreGig } from '../api'
import { ErrorBox, Pill, RemovedPill, SkeletonBlock, dangerButton, quietButton } from '../components/ui'
import { GIG_STATUS, formatBudget, formatDate, formatDateTime } from '../format'
import { useAdminData } from '../useAdminData'
import { useModeration } from '../useModeration'
import { GigModerationDialogs } from './GigsPage'

export default function GigPreviewPage() {
  const { id } = useParams()
  const { data: gig, setData, error, loading, reload } = useAdminData(() => fetchGig(id), id)
  const moderation = useModeration({
    remove: removeGig,
    restore: restoreGig,
    onUpdated: (row) => setData((current) => ({ ...current, ...row })),
    describe: (row) => `"${row.title}"`,
  })

  if (error) return <ErrorBox onRetry={reload}>{error}</ErrorBox>
  if (loading && !gig) return <SkeletonBlock className="h-96" />

  const removed = gig.moderation_status === 'removed'
  return (
    <div className="space-y-4">
      <Link to="/admin/gigs" className="text-body text-primary font-semibold hover:underline">
        Back to gigs
      </Link>
      <article className="bg-surface rounded-card shadow-hairline p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap gap-2 mb-2">
              <Pill tone="ocean">{gig.category}</Pill>
              <Pill>{GIG_STATUS[gig.status]}</Pill>
              {removed && <RemovedPill />}
              {gig.is_synthetic && <Pill>Synthetic</Pill>}
            </div>
            <h1 className="text-page-title text-ink break-words">{gig.title}</h1>
            <p className="text-body text-ink-soft mt-1">
              Posted {formatDate(gig.created_at)} by{' '}
              <Link to={`/admin/users/${gig.client.id}`} className="text-primary font-semibold hover:underline">
                {gig.client.full_name}
              </Link>
              {gig.client_status === 'suspended' && ' (suspended)'}
            </p>
          </div>
          {removed ? (
            <button type="button" className={quietButton} onClick={() => moderation.askRestore(gig)}>
              Restore gig
            </button>
          ) : (
            <button type="button" className={dangerButton} onClick={() => moderation.askRemove(gig)}>
              Remove gig
            </button>
          )}
        </div>

        {removed && (
          <p className="mt-4 rounded-input bg-coral-light text-coral-ink px-4 py-3 text-body">
            Removed {formatDateTime(gig.removed_at)}. Reason: {gig.removed_reason}
          </p>
        )}

        <dl className="grid gap-4 sm:grid-cols-3 mt-6">
          <div>
            <dt className="text-caption text-muted">Budget</dt>
            <dd className="text-body text-ink">
              {formatBudget(gig)} {gig.is_negotiable ? '(negotiable)' : '(fixed)'}
            </dd>
          </div>
          <div>
            <dt className="text-caption text-muted">Apply by</dt>
            <dd className="text-body text-ink">{formatDate(gig.application_deadline)}</dd>
          </div>
          <div>
            <dt className="text-caption text-muted">Location</dt>
            <dd className="text-body text-ink">{gig.is_remote ? 'Remote' : gig.county || 'Not given'}</dd>
          </div>
        </dl>

        <h2 className="text-section-title text-ink mt-6 mb-2">Description</h2>
        <p className="text-body text-prose whitespace-pre-line break-words">{gig.description}</p>

        {gig.skills.length > 0 && (
          <ul className="flex flex-wrap gap-2 mt-4" aria-label="Skills">
            {gig.skills.map((skill) => (
              <li key={skill} className="text-caption bg-sand text-ink-soft px-3 py-1 rounded-pill">
                {skill}
              </li>
            ))}
          </ul>
        )}

        <Link
          to={`/admin/applications?gig=${gig.id}`}
          className="inline-block mt-6 text-body text-primary font-semibold hover:underline"
        >
          See its {gig.application_count} application{gig.application_count === 1 ? '' : 's'}
        </Link>
      </article>
      <GigModerationDialogs moderation={moderation} />
    </div>
  )
}
