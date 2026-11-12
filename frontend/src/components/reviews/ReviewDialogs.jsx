import { useId, useState } from 'react'
import { REVIEW_MAX_LENGTH, createReview, reviewError, updateReview } from '../../api/reviews'
import Button from '../Button'
import Modal from '../Modal'
import StarInput from './StarInput'

export const RATING_NOT_SAVED = "Gig completed, but your rating wasn't saved. Try again from My gigs."

// The stars and the optional words, shared by both dialogs.
function ReviewFields({ name, rating, onRating, text, onText, optional = false, disabled = false }) {
  const textId = useId()
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <StarInput value={rating} onChange={onRating} label={`Your rating of ${name}`} disabled={disabled} />
        {optional && rating > 0 && (
          <button type="button" onClick={() => onRating(0)} className="text-label text-primary hover:underline">
            Clear rating
          </button>
        )}
      </div>
      <label htmlFor={textId} className="block text-label text-ink mt-3">
        Review <span className="text-muted font-normal">(optional)</span>
      </label>
      <textarea
        id={textId}
        value={text}
        onChange={(e) => onText(e.target.value)}
        maxLength={REVIEW_MAX_LENGTH}
        rows={3}
        disabled={disabled}
        placeholder={`How was working with ${name}?`}
        className="mt-1.5 w-full rounded-input border border-border bg-surface px-3 py-2.5 text-body text-ink focus:outline-none focus:ring-2 focus:ring-primary"
      />
      <p className="text-caption text-muted text-right">
        {text.length.toLocaleString('en-US')} / {REVIEW_MAX_LENGTH.toLocaleString('en-US')}
      </p>
    </div>
  )
}

/*
  "Mark as completed". The rating is optional: with no stars chosen the gig is just completed, and "Rate <name>"
  stays in My gigs for 14 days. The gig is completed first and the rating saved second, so a rating that fails never
  undoes the completion; onDone is told so the page can say so.
*/
export function CompleteGigDialog({ gig, freelancerName, onComplete, onDone, onCancel }) {
  const [rating, setRating] = useState(0)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    if (text.trim() && !rating) {
      setError('Choose 1 to 5 stars to send your review, or clear the text to skip it.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await onComplete()
    } catch (err) {
      setError(err?.response?.data?.status?.[0] || 'Could not mark this gig as completed.')
      setBusy(false)
      return
    }
    let ratingFailed = false
    if (rating) {
      try {
        await createReview(gig.id, { rating, text: text.trim() })
      } catch {
        ratingFailed = true
      }
    }
    onDone({ rated: Boolean(rating) && !ratingFailed, ratingFailed })
  }

  return (
    <Modal
      title={`Mark "${gig.title}" as completed?`}
      description="The work is done and the gig closes. This can't be changed back."
      onClose={onCancel}
      busy={busy}
      wide
    >
      <form onSubmit={submit} className="mt-5" noValidate>
        {freelancerName && (
          <fieldset className="rounded-tile bg-sand p-4">
            <legend className="float-left w-full text-label text-ink mb-2">
              Rate {freelancerName} <span className="text-muted font-normal">(optional)</span>
            </legend>
            <ReviewFields
              name={freelancerName}
              rating={rating}
              onRating={setRating}
              text={text}
              onText={setText}
              optional
              disabled={busy}
            />
            <p className="text-caption text-muted">
              You can skip this and rate from My gigs for 14 days. Ratings are public on their profile.
            </p>
          </fieldset>
        )}
        {error && (
          <p role="alert" className="text-caption text-coral-ink mt-3">
            {error}
          </p>
        )}
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            {rating ? 'Complete and rate' : 'Mark as completed'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

/*
  Rating a completed gig from My gigs, or changing a review, within 14 days of completion. Stars are required here.
*/
export function ReviewDialog({ gig, freelancerName, review = null, onSaved, onCancel }) {
  const [rating, setRating] = useState(review?.rating || 0)
  const [text, setText] = useState(review?.text || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    if (!rating) {
      setError('Choose 1 to 5 stars.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const body = { rating, text: text.trim() }
      onSaved(await (review ? updateReview(gig.id, body) : createReview(gig.id, body)))
    } catch (err) {
      setError(reviewError(err, 'Could not save your review. Try again.'))
      setBusy(false)
    }
  }

  return (
    <Modal
      title={review ? `Edit your review of ${freelancerName}` : `Rate ${freelancerName}`}
      description={`For "${gig.title}". Your rating is public on their profile, and they can reply once.`}
      onClose={onCancel}
      busy={busy}
      wide
    >
      <form onSubmit={submit} className="mt-5" noValidate>
        <ReviewFields name={freelancerName} rating={rating} onRating={setRating} text={text} onText={setText} disabled={busy} />
        {error && (
          <p role="alert" className="text-caption text-coral-ink mt-2">
            {error}
          </p>
        )}
        <div className="mt-5 flex flex-wrap justify-end gap-3">
          <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            {review ? 'Save changes' : 'Send rating'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
