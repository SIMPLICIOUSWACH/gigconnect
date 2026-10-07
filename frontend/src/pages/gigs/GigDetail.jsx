import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { fetchGig } from '../../api/gigs'
import Alert from '../../components/Alert'
import ApplyForm from '../../components/applications/ApplyForm'
import StatusBadge from '../../components/applications/StatusBadge'
import Button from '../../components/Button'
import Card from '../../components/Card'
import { useAuth } from '../../context/AuthContext'
import { formatDate, isApplicationClosed } from '../../utils/gigFormat'

const STATUS_LABELS = {
  open: { text: 'Open', className: 'bg-accent-light text-accent' },
  in_progress: { text: 'In Progress', className: 'bg-primary-light text-primary' },
  completed: { text: 'Completed', className: 'bg-bg text-muted' },
  closed: { text: 'Closed', className: 'bg-red-50 text-red-700' },
}

export default function GigDetail() {
  const { id } = useParams()
  const location = useLocation()
  const { user } = useAuth()
  const [gig, setGig] = useState(null)
  const [error, setError] = useState('')
  const [applying, setApplying] = useState(false)

  useEffect(() => {
    fetchGig(id).then(setGig).catch(() => setError('Could not load this gig.'))
  }, [id])

  if (error) return <Alert type="error">{error}</Alert>
  if (!gig) return <p className="text-body text-muted">Loading…</p>

  const statusInfo = STATUS_LABELS[gig.status]
  const applicationsClosed = isApplicationClosed(gig.application_deadline)
  const backTo = location.state?.from

  return (
    <div className="max-w-[720px]">
      {backTo && (
        <Link to={backTo} className="inline-block text-body text-primary font-medium mb-4">
          Back to results
        </Link>
      )}
      <Card variant="elevated">
        <div className="flex items-start justify-between gap-4 mb-2">
          <h1 className="text-page-title text-primary">{gig.title}</h1>
          <span className={`text-caption font-medium px-2.5 py-1 rounded-full shrink-0 ${statusInfo.className}`}>
            {statusInfo.text}
          </span>
        </div>

        <p className="text-body text-muted mb-6">
          Posted by{' '}
          <Link to={`/profile/${gig.client.id}`} className="text-primary font-medium">
            {gig.client.company_name || gig.client.full_name}
          </Link>{' '}
          · {gig.category.name}
          {(gig.county || gig.is_remote) &&
            ` · ${[gig.county, gig.is_remote && 'Remote'].filter(Boolean).join(', ')}`}
          {' '}· {gig.view_count} view{gig.view_count === 1 ? '' : 's'}
        </p>

        <p className="text-body text-ink whitespace-pre-wrap mb-6">{gig.description}</p>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <p className="text-label text-muted mb-1">Budget</p>
            <p className="text-body text-ink">
              {gig.currency} {gig.budget_min} – {gig.budget_max}
              {gig.is_negotiable && <span className="text-muted"> (Negotiable)</span>}
            </p>
          </div>
          <div>
            <p className="text-label text-muted mb-1">Project deadline</p>
            <p className="text-body text-ink">{formatDate(gig.deadline)}</p>
          </div>
          <div>
            <p className="text-label text-muted mb-1">Application deadline</p>
            <p className="text-body text-ink">{formatDate(gig.application_deadline)}</p>
          </div>
        </div>

        <div className="mb-6">
          <p className="text-label text-muted mb-2">Required skills</p>
          <div className="flex flex-wrap gap-2">
            {gig.skills.map((skill) => (
              <span
                key={skill.id}
                className="text-caption font-medium px-3 py-1.5 rounded-full bg-primary-light text-primary"
              >
                {skill.name}
              </span>
            ))}
          </div>
        </div>

        <ApplySection
          gig={gig}
          user={user}
          applicationsClosed={applicationsClosed}
          applying={applying}
          onStartApplying={() => setApplying(true)}
          onCancel={() => setApplying(false)}
          onApplied={(application) => {
            setApplying(false)
            setGig((current) => ({ ...current, my_application: { id: application.id, status: application.status } }))
          }}
        />
      </Card>
    </div>
  )
}

/** The Apply area at the bottom of a gig: what a visitor sees depends on who they are and the gig's state. */
function ApplySection({ gig, user, applicationsClosed, applying, onStartApplying, onCancel, onApplied }) {
  if (user?.role !== 'freelancer') return null

  if (gig.my_application) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-body text-ink font-medium">
          {gig.my_application.status === 'withdrawn' ? 'You withdrew your application' : 'Applied'}
        </span>
        <StatusBadge status={gig.my_application.status} />
        <Link to={`/applications/${gig.my_application.id}`} className="text-body text-primary font-medium">
          View your application
        </Link>
      </div>
    )
  }

  if (gig.status !== 'open') return <Alert type="info">This gig is no longer accepting applications.</Alert>
  if (applicationsClosed) {
    return <Alert type="info">Applications closed on {formatDate(gig.application_deadline)}.</Alert>
  }
  if (!user.is_email_verified) return <Alert type="info">Verify your email address to apply to gigs.</Alert>

  if (applying) {
    return <ApplyForm gigId={gig.id} currency={gig.currency} onApplied={onApplied} onCancel={onCancel} />
  }
  return <Button onClick={onStartApplying}>Apply</Button>
}
