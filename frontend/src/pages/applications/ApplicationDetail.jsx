import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchApplication, withdrawApplication } from '../../api/applications'
import Alert from '../../components/Alert'
import StatusBadge from '../../components/applications/StatusBadge'
import Button from '../../components/Button'
import Card from '../../components/Card'
import Label from '../../components/Label'
import { formatDateTime, statusLabel } from '../../utils/applicationStatus'

export default function ApplicationDetail() {
  const { id } = useParams()
  const [application, setApplication] = useState(null)
  const [error, setError] = useState('')
  const [notFound, setNotFound] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [reason, setReason] = useState('')
  const [withdrawing, setWithdrawing] = useState(false)
  const [withdrawError, setWithdrawError] = useState('')

  const load = useCallback(() => {
    setError('')
    fetchApplication(id)
      .then(setApplication)
      .catch((err) => {
        if (err.response?.status === 404) setNotFound(true)
        else setError('Could not load this application.')
      })
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  const handleWithdraw = async () => {
    setWithdrawing(true)
    setWithdrawError('')
    try {
      setApplication(await withdrawApplication(id, reason.trim()))
      setConfirming(false)
    } catch (err) {
      setWithdrawError(err.response?.data?.detail || 'Could not withdraw your application. Please try again.')
    } finally {
      setWithdrawing(false)
    }
  }

  if (notFound) return <Alert type="error">This application does not exist, or you cannot see it.</Alert>
  if (error) {
    return (
      <div className="space-y-3">
        <Alert type="error">{error}</Alert>
        <Button variant="secondary" onClick={load}>
          Try again
        </Button>
      </div>
    )
  }
  if (!application) return <p className="text-body text-muted">Loading…</p>

  // The server says what the signed-in person may do, so the button never offers a move that would fail.
  const canWithdraw = application.allowed_next_statuses.includes('withdrawn')

  return (
    <div className="max-w-[720px]">
      <Link to={`/gigs/${application.gig_id}`} className="inline-block text-body text-primary font-medium mb-4">
        View the gig
      </Link>
      <Card variant="elevated">
        <div className="flex items-start justify-between gap-4 mb-2">
          <h1 className="text-page-title text-primary">{application.gig_title}</h1>
          <StatusBadge status={application.status} />
        </div>
        <p className="text-body text-muted mb-6">
          {application.client_name} · Applied {formatDateTime(application.created_at)}
        </p>

        <div className="mb-6">
          <Label>Cover letter</Label>
          <p className="text-body text-ink whitespace-pre-wrap">{application.cover_letter}</p>
        </div>

        {(application.portfolio_link || application.proposed_rate) && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            {application.portfolio_link && (
              <div>
                <Label>Portfolio link</Label>
                <a
                  href={application.portfolio_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-body text-primary break-all"
                >
                  {application.portfolio_link}
                </a>
              </div>
            )}
            {application.proposed_rate && (
              <div>
                <Label>Proposed rate</Label>
                <p className="text-body text-ink">KES {Number(application.proposed_rate).toLocaleString('en-US')}</p>
              </div>
            )}
          </div>
        )}

        <div className="mb-6">
          <Label>History</Label>
          <ol className="space-y-2">
            {application.events.map((event) => (
              <li key={event.id} className="text-body text-ink">
                {event.from_status ? (
                  <>
                    {statusLabel(event.from_status)} to {statusLabel(event.to_status)}
                  </>
                ) : (
                  <>Applied</>
                )}
                <span className="text-muted">
                  {' '}
                  · {formatDateTime(event.created_at)} · {event.changed_by_name}
                </span>
                {event.note && <p className="text-caption text-muted">Note: {event.note}</p>}
              </li>
            ))}
          </ol>
        </div>

        {canWithdraw && !confirming && (
          <Button variant="secondary" onClick={() => setConfirming(true)}>
            Withdraw application
          </Button>
        )}

        {canWithdraw && confirming && (
          <div className="border border-border rounded-lg p-5 space-y-4" role="group" aria-label="Confirm withdrawal">
            <p className="text-body text-ink">
              Withdraw your application? You will not be able to apply to this gig again.
            </p>
            <label className="block">
              <Label>Reason (optional)</Label>
              <textarea
                rows={3}
                maxLength={500}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full px-4 py-3 border border-border rounded-lg text-body text-ink bg-surface focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
            </label>
            <Alert type="error">{withdrawError}</Alert>
            <div className="flex gap-3">
              <Button variant="danger" onClick={handleWithdraw} loading={withdrawing}>
                Yes, withdraw
              </Button>
              <Button variant="secondary" onClick={() => setConfirming(false)} disabled={withdrawing}>
                Keep my application
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
