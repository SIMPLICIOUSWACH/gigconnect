import { useEffect, useId, useState } from 'react'
import { Star } from 'lucide-react'
import { REPLY_MAX_LENGTH, fetchFreelancerReviews, replyToReview, reviewError } from '../../api/reviews'
import Button from '../Button'
import RatingSummary from './RatingSummary'
import { starLabel } from './StarInput'

const PAGE_SIZE = 5

const dateOf = (iso) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

function Stars({ rating }) {
  return (
    <span role="img" aria-label={starLabel(rating)} className="inline-flex gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          size={16}
          aria-hidden="true"
          className={star <= rating ? 'fill-sun text-sun' : 'fill-transparent text-toggle-off'}
        />
      ))}
    </span>
  )
}

// The rated freelancer's one reply to a review.
function ReplyForm({ review, onReplied }) {
  const [open, setOpen] = useState(false)
  const [reply, setReply] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const inputId = useId()

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="mt-2 text-label text-primary hover:underline">
        Reply
      </button>
    )
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!reply.trim()) {
      setError('Write a reply first.')
      return
    }
    setBusy(true)
    setError('')
    try {
      onReplied(await replyToReview(review.id, reply.trim()))
    } catch (err) {
      setError(reviewError(err, 'Could not post your reply. Try again.'))
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="mt-3" noValidate>
      <label htmlFor={inputId} className="block text-label text-ink">
        Your reply
      </label>
      <p className="text-caption text-muted">Public, and you can only reply once.</p>
      <textarea
        id={inputId}
        value={reply}
        onChange={(e) => setReply(e.target.value)}
        maxLength={REPLY_MAX_LENGTH}
        rows={3}
        className="mt-1.5 w-full rounded-input border border-border bg-surface px-3 py-2.5 text-body text-ink focus:outline-none focus:ring-2 focus:ring-primary"
      />
      <p className="text-caption text-muted text-right">
        {reply.length} / {REPLY_MAX_LENGTH}
      </p>
      {error && (
        <p role="alert" className="text-caption text-coral-ink">
          {error}
        </p>
      )}
      <div className="mt-2 flex gap-3">
        <Button type="submit" loading={busy} className="min-h-[40px] px-4">
          Post reply
        </Button>
        <Button type="button" variant="secondary" onClick={() => setOpen(false)} disabled={busy} className="min-h-[40px] px-4">
          Cancel
        </Button>
      </div>
    </form>
  )
}

/*
  A freelancer's reviews on their public profile: the average and count, then each review with the gig, the client,
  the date, the words and the freelancer's reply. Removed reviews never reach this list.
*/
export default function ReviewList({ freelancerId, freelancerName, average, count }) {
  const [reviews, setReviews] = useState(null)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    fetchFreelancerReviews(freelancerId, { page, page_size: PAGE_SIZE })
      .then((data) => {
        if (!alive) return
        setReviews((current) => (page === 1 ? data.results : [...(current || []), ...data.results]))
        setHasMore(data.page < data.total_pages)
      })
      .catch(() => alive && setError(true))
    return () => {
      alive = false
    }
  }, [freelancerId, page])

  const replaced = (updated) =>
    setReviews((current) => current.map((review) => (review.id === updated.id ? updated : review)))

  return (
    <section aria-labelledby="reviews-heading" id="reviews">
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <h2 id="reviews-heading" className="text-section-title text-ink">
          Reviews
        </h2>
        <RatingSummary average={average} count={count} />
      </div>

      {error && <p className="text-body text-coral-ink">Could not load the reviews.</p>}
      {!error && reviews === null && (
        <ul aria-label="Loading reviews" className="space-y-3">
          {[0, 1].map((i) => (
            <li key={i} aria-hidden="true" className="h-24 rounded-tile bg-track animate-pulse" />
          ))}
        </ul>
      )}
      {reviews?.length === 0 && (
        <p className="text-body text-muted">
          No reviews yet. Clients can rate {freelancerName || 'this freelancer'} after a gig is completed.
        </p>
      )}

      {reviews?.length > 0 && (
        <ul className="space-y-3">
          {reviews.map((review) => (
            <li key={review.id} className="rounded-tile border border-line p-4">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <Stars rating={review.rating} />
                <span className="text-label text-ink">{review.client_name}</span>
                <span className="text-caption text-muted">
                  {dateOf(review.created_at)}
                  {review.edited && ' · edited'}
                </span>
              </div>
              <p className="text-caption text-muted mt-1">For &quot;{review.gig_title}&quot;</p>
              {review.text && <p className="text-body text-prose mt-2 whitespace-pre-line break-words">{review.text}</p>}
              {review.reply && (
                <div className="mt-3 rounded-input bg-sand px-4 py-3">
                  <p className="text-label text-ink">
                    Reply from {freelancerName || 'the freelancer'}
                    {review.reply_at && <span className="text-caption text-muted font-normal"> · {dateOf(review.reply_at)}</span>}
                  </p>
                  <p className="text-body text-prose mt-1 whitespace-pre-line break-words">{review.reply}</p>
                </div>
              )}
              {review.can_reply && <ReplyForm review={review} onReplied={replaced} />}
            </li>
          ))}
        </ul>
      )}

      {hasMore && (
        <div className="mt-4 text-center">
          <Button variant="secondary" onClick={() => setPage((n) => n + 1)}>
            Show more reviews
          </Button>
        </div>
      )}
    </section>
  )
}
