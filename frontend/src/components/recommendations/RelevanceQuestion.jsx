import { useState } from 'react'
import { setRelevance } from '../../api/recommendations'

const SAVED_MESSAGE = 'Thanks, noted'
const ERROR_MESSAGE = 'Could not save your answer. Try again.'

/**
 * "Is this gig relevant to you?" under a recommended gig. The answer is stored for user acceptance testing and never
 * feeds the recommender. It can be changed: a new answer replaces the old one. `initial` is the answer the server
 * already has, if any.
 */
export default function RelevanceQuestion({ gigId, gigTitle, position, initial = null }) {
  const [answer, setAnswer] = useState(initial)
  const [status, setStatus] = useState(initial ? 'saved' : 'idle') // idle | saving | saved | error

  const choose = (relevant) => {
    setStatus('saving')
    setRelevance(gigId, relevant, position)
      .then((data) => {
        setAnswer(data.relevance)
        setStatus('saved')
      })
      .catch(() => setStatus('error'))
  }

  const option = (value, label, relevant) => (
    <button
      type="button"
      onClick={() => choose(relevant)}
      disabled={status === 'saving'}
      aria-pressed={answer === value}
      className={`text-caption font-medium px-3 py-1 rounded-full border transition-colors disabled:opacity-50 ${
        answer === value ? 'bg-primary text-white border-primary' : 'bg-surface text-ink border-border hover:bg-bg'
      }`}
    >
      {label}
    </button>
  )

  return (
    <div role="group" aria-label={`Is ${gigTitle} relevant to you?`} className="flex flex-wrap items-center gap-2 px-1">
      <span className="text-caption text-muted">Is this gig relevant to you?</span>
      {option('relevant', 'Relevant', true)}
      {option('not_relevant', 'Not relevant', false)}
      <span role="status" aria-live="polite" className="text-caption text-muted">
        {status === 'saved' && SAVED_MESSAGE}
        {status === 'error' && <span className="text-red-600">{ERROR_MESSAGE}</span>}
      </span>
    </div>
  )
}
