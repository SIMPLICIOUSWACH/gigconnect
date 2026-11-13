import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { deleteGig, fetchMyGigs, updateGigStatus } from '../../api/gigs'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
import SuggestedFreelancers from '../../components/freelancers/SuggestedFreelancers'
import { MessageFreelancerButton } from '../../components/messages/ChatLinks'
import { CompleteGigDialog, RATING_NOT_SAVED, ReviewDialog } from '../../components/reviews/ReviewDialogs'
import { starLabel } from '../../components/reviews/StarInput'

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
    { value: 'completed', label: 'Mark as completed' },
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
  // { kind: 'complete' | 'rate', gig }: the completion dialog, or rating a completed gig (or editing the review).
  const [dialog, setDialog] = useState(null)
  const [notice, setNotice] = useState('')

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

  const finishCompleting = async ({ rated, ratingFailed }) => {
    const name = dialog.gig.chats?.[0]?.freelancer_name
    setDialog(null)
    setNotice('')
    await load()
    if (ratingFailed) setError(RATING_NOT_SAVED)
    else setNotice(rated ? `Gig completed, and your rating of ${name} was saved.` : 'Gig completed.')
  }

  const finishRating = async () => {
    const editing = Boolean(dialog.gig.rating?.review)
    setDialog(null)
    setError('')
    await load()
    setNotice(editing ? 'Your review was updated.' : 'Thanks. Your rating was saved.')
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

      {notice && (
        <div className="mb-4" role="status">
          <Alert type="success">{notice}</Alert>
        </div>
      )}

      {gigs === null && <p className="text-body text-muted">Loading…</p>}
      {gigs?.length === 0 && <p className="text-body text-muted">You haven't posted any gigs yet.</p>}

      <div className="space-y-4">
        {gigs?.map((gig) => {
          const statusInfo = STATUS_LABELS[gig.status]
          const nextOptions = NEXT_STATUSES[gig.status] || []
          const busy = busyId === gig.id
          const removed = gig.moderation_status === 'removed'
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
                {removed ? (
                  <span className="text-caption font-semibold px-2.5 py-1 rounded-full shrink-0 bg-coral-light text-coral-ink">
                    Removed
                  </span>
                ) : (
                  <span className={`text-caption font-medium px-2.5 py-1 rounded-full shrink-0 ${statusInfo.className}`}>
                    {statusInfo.text}
                  </span>
                )}
              </div>

              {removed && (
                <p className="mt-3 text-body text-coral-ink bg-coral-light rounded-input px-4 py-3">
                  An administrator removed this gig, so freelancers can't see it and it can't be changed.
                  {gig.removed_reason && ` Reason: ${gig.removed_reason}`}
                </p>
              )}

              {!removed && gig.status === 'open' && <SuggestedFreelancers gigId={gig.id} collapsed />}

              {!removed && gig.rating && (gig.rating.can_rate || gig.rating.review) && (
                <div className="flex flex-wrap items-center gap-3 mt-4 rounded-input bg-sand px-4 py-3">
                  {gig.rating.review ? (
                    <>
                      <p className="text-body text-ink">
                        You gave {gig.rating.freelancer_name} {starLabel(gig.rating.review.rating)}.
                        {gig.rating.review.removed && ' An administrator removed this review.'}
                      </p>
                      {gig.rating.can_edit && (
                        <Button
                          variant="secondary"
                          className="py-1.5 px-3 text-caption"
                          onClick={() => setDialog({ kind: 'rate', gig })}
                        >
                          Edit review
                        </Button>
                      )}
                    </>
                  ) : (
                    <>
                      <p className="text-body text-ink">How was working with {gig.rating.freelancer_name}?</p>
                      <Button className="py-1.5 px-3 text-caption" onClick={() => setDialog({ kind: 'rate', gig })}>
                        Rate {gig.rating.freelancer_name}
                      </Button>
                    </>
                  )}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-3 mt-4 pt-4 border-t border-border">
                {gig.chats?.map((chat) => (
                  <MessageFreelancerButton
                    key={chat.conversation_id}
                    conversationId={chat.conversation_id}
                    name={chat.freelancer_name}
                    started={chat.started}
                    size="sm"
                  />
                ))}
                <Link to={`/gigs/${gig.id}/applicants`} className="text-body text-primary font-medium">
                  {gig.application_count} applicant{gig.application_count === 1 ? '' : 's'}
                  {gig.pending_application_count > 0 && ` (${gig.pending_application_count} pending)`}
                </Link>
                {!removed && gig.status === 'open' && (
                  <Link to={`/gigs/${gig.id}/edit`} className="text-body text-primary font-medium">
                    Edit
                  </Link>
                )}
                {!removed && nextOptions.map((opt) => (
                  <Button
                    key={opt.value}
                    variant="secondary"
                    className="py-1.5 px-3 text-caption"
                    disabled={busy}
                    onClick={() =>
                      opt.value === 'completed'
                        ? setDialog({ kind: 'complete', gig })
                        : handleStatusChange(gig.id, opt.value)
                    }
                  >
                    {opt.label}
                  </Button>
                ))}

                {removed ? null : confirmDeleteId === gig.id ? (
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
      {dialog?.kind === 'complete' && (
        <CompleteGigDialog
          gig={dialog.gig}
          freelancerName={dialog.gig.chats?.[0]?.freelancer_name}
          onComplete={() => updateGigStatus(dialog.gig.id, 'completed')}
          onDone={finishCompleting}
          onCancel={() => setDialog(null)}
        />
      )}
      {dialog?.kind === 'rate' && (
        <ReviewDialog
          gig={dialog.gig}
          freelancerName={dialog.gig.rating.freelancer_name}
          review={dialog.gig.rating.review}
          onSaved={finishRating}
          onCancel={() => setDialog(null)}
        />
      )}
    </div>
  )
}
