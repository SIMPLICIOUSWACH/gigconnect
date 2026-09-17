import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { deleteGig, fetchMyGigs, updateGigStatus } from '../../api/gigs'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'

const STATUS_LABELS = {
  open: { text: 'Open', className: 'bg-accent-light text-accent' },
  in_progress: { text: 'In Progress', className: 'bg-primary-light text-primary' },
  completed: { text: 'Completed', className: 'bg-bg text-muted' },
  closed: { text: 'Closed', className: 'bg-red-50 text-red-700' },
}

const NEXT_STATUSES = {
  open: [
    { value: 'in_progress', label: 'Start' },
    { value: 'closed', label: 'Cancel' },
  ],
  in_progress: [
    { value: 'completed', label: 'Complete' },
    { value: 'closed', label: 'Cancel' },
  ],
  completed: [],
  closed: [],
}

export default function MyGigs() {
  const [gigs, setGigs] = useState(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)

  const load = () => fetchMyGigs().then(setGigs).catch(() => setError('Could not load your gigs.'))

  useEffect(() => {
    load()
  }, [])

  const handleStatusChange = async (gigId, statusValue) => {
    setError('')
    setBusyId(gigId)
    try {
      await updateGigStatus(gigId, statusValue)
      await load()
    } catch (err) {
      setError(err.response?.data?.status?.[0] || 'Could not change status.')
    } finally {
      setBusyId(null)
    }
  }

  const handleDelete = async (gigId) => {
    setError('')
    setBusyId(gigId)
    try {
      await deleteGig(gigId)
      await load()
    } catch {
      setError('Could not delete this gig.')
    } finally {
      setBusyId(null)
      setConfirmDeleteId(null)
    }
  }

  return (
    <div className="max-w-[960px]">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-page-title text-primary">My Gigs</h1>
        <Link to="/gigs/new">
          <Button>Post a gig</Button>
        </Link>
      </div>

      {error && (
        <div className="mb-4">
          <Alert type="error">{error}</Alert>
        </div>
      )}

      {gigs === null && <p className="text-body text-muted">Loading…</p>}
      {gigs?.length === 0 && <p className="text-body text-muted">You haven't posted any gigs yet.</p>}

      <div className="space-y-4">
        {gigs?.map((gig) => {
          const statusInfo = STATUS_LABELS[gig.status]
          const nextOptions = NEXT_STATUSES[gig.status] || []
          const busy = busyId === gig.id
          return (
            <Card key={gig.id}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <Link to={`/gigs/${gig.id}`} className="text-section-title text-ink hover:text-primary">
                    {gig.title}
                  </Link>
                  <p className="text-body text-muted mt-1">
                    {gig.category.name} · KES {gig.budget_min}–{gig.budget_max} · Deadline {gig.deadline}
                  </p>
                </div>
                <span className={`text-caption font-medium px-2.5 py-1 rounded-full shrink-0 ${statusInfo.className}`}>
                  {statusInfo.text}
                </span>
              </div>

              <div className="flex items-center gap-3 mt-4 pt-4 border-t border-border">
                {gig.status === 'open' && (
                  <Link to={`/gigs/${gig.id}/edit`} className="text-body text-primary font-medium">
                    Edit
                  </Link>
                )}
                {nextOptions.map((opt) => (
                  <Button
                    key={opt.value}
                    variant="secondary"
                    className="py-1.5 px-3 text-caption"
                    disabled={busy}
                    onClick={() => handleStatusChange(gig.id, opt.value)}
                  >
                    {opt.label}
                  </Button>
                ))}

                {confirmDeleteId === gig.id ? (
                  <span className="flex items-center gap-2 ml-auto">
                    <span className="text-caption text-muted">Delete this gig?</span>
                    <Button
                      variant="danger"
                      className="py-1.5 px-3 text-caption"
                      loading={busy}
                      onClick={() => handleDelete(gig.id)}
                    >
                      Confirm
                    </Button>
                    <Button
                      variant="secondary"
                      className="py-1.5 px-3 text-caption"
                      onClick={() => setConfirmDeleteId(null)}
                    >
                      Cancel
                    </Button>
                  </span>
                ) : (
                  <button
                    onClick={() => setConfirmDeleteId(gig.id)}
                    className="text-caption text-red-600 font-medium ml-auto"
                  >
                    Delete
                  </button>
                )}
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
