import { useEffect, useRef, useState } from 'react'
import { applyToGig } from '../../api/applications'
import {
  buildApplicationPayload,
  COVER_LETTER_MAX,
  COVER_LETTER_MIN,
  readApplicationError,
  validateApplication,
} from '../../utils/applicationForm'
import Alert from '../Alert'
import Button from '../Button'
import Input from '../Input'
import Label from '../Label'

export default function ApplyForm({ gigId, currency = 'KES', onApplied, onCancel }) {
  const [coverLetter, setCoverLetter] = useState('')
  const [portfolioLink, setPortfolioLink] = useState('')
  const [proposedRate, setProposedRate] = useState('')
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const letterRef = useRef(null)

  useEffect(() => {
    letterRef.current?.focus()
  }, [])

  const length = coverLetter.trim().length
  const counterTone = length > COVER_LETTER_MAX ? 'text-red-600' : 'text-muted'

  const handleSubmit = async (event) => {
    event.preventDefault()
    setFormError('')
    const values = { coverLetter, portfolioLink, proposedRate }
    const found = validateApplication(values)
    setErrors(found)
    if (Object.keys(found).length > 0) {
      if (found.cover_letter) letterRef.current?.focus()
      return
    }

    setSubmitting(true)
    try {
      const application = await applyToGig(gigId, buildApplicationPayload(values))
      onApplied(application)
    } catch (err) {
      const { fields, message } = readApplicationError(err)
      setErrors(fields)
      setFormError(message)
      if (fields.cover_letter) letterRef.current?.focus()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="mt-2 space-y-5" aria-label="Apply to this gig">
      <h2 className="text-section-title text-ink">Apply to this gig</h2>
      <Alert type="error">{formError}</Alert>

      <div>
        <label htmlFor="cover-letter">
          <Label required>Cover letter</Label>
        </label>
        <textarea
          id="cover-letter"
          ref={letterRef}
          rows={7}
          value={coverLetter}
          onChange={(e) => setCoverLetter(e.target.value)}
          aria-invalid={Boolean(errors.cover_letter)}
          aria-describedby="cover-letter-help"
          placeholder="Tell the client why you are a good fit and how you would approach the work."
          className={`w-full px-4 py-3 border rounded-lg text-body text-ink bg-surface placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors ${
            errors.cover_letter ? 'border-red-400' : 'border-border'
          }`}
        />
        <div id="cover-letter-help" className="flex justify-between gap-4 mt-1.5">
          <span className="text-caption text-red-600" role={errors.cover_letter ? 'alert' : undefined}>
            {errors.cover_letter}
          </span>
          <span className={`text-caption shrink-0 ${counterTone}`}>
            {length} / {COVER_LETTER_MAX} (at least {COVER_LETTER_MIN})
          </span>
        </div>
      </div>

      <Input
        label="Portfolio link (optional)"
        type="url"
        inputMode="url"
        value={portfolioLink}
        onChange={(e) => setPortfolioLink(e.target.value)}
        error={errors.portfolio_link}
        placeholder="https://example.com/my-work"
      />

      <Input
        label={`Proposed rate in ${currency} (optional)`}
        type="number"
        inputMode="decimal"
        min="0"
        step="any"
        value={proposedRate}
        onChange={(e) => setProposedRate(e.target.value)}
        error={errors.proposed_rate}
        placeholder="For example 15000"
      />

      <div className="flex gap-3">
        <Button type="submit" loading={submitting}>
          Send application
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
