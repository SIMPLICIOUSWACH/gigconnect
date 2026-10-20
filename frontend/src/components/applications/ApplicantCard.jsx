import { BadgeCheck } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ACTION_LABELS, CONFIRMED_ACTIONS, formatDateTime, statusLabel } from '../../utils/applicationStatus'
import Alert from '../Alert'
import Button from '../Button'
import Label from '../Label'
import StatusBadge from './StatusBadge'

const CONSEQUENCES = {
  hired: 'Hiring moves this gig to In progress. Other applicants are not changed.',
  rejected: 'The applicant will see that they were not selected.',
}

const BAND_LABELS = {
  strong: 'Strong skill overlap',
  good: 'Good skill overlap',
  some: 'Some skill overlap',
}

/**
 * How well the applicant's skills match this gig, as worked out by the trained model for this exact
 * applicant and gig. Nothing is shown unless the API sent it: with no score the card says so plainly, and
 * it never turns a missing score into a low one. The styling is the same for every band, so no colour
 * suggests more certainty than the model has.
 */
function SkillMatch({ application }) {
  const { match_score: score, match_band: band, match_reasons: shared } = application
  let text
  if (band) text = <span className="font-medium text-ink">{BAND_LABELS[band]}</span>
  else if (score !== null && score !== undefined) text = <span>No shared skills with this gig</span>
  else text = <span>Match score not available</span>

  return (
    <div className="text-caption text-muted border border-border rounded-lg px-3 py-2 mb-4">
      <p>
        Skill match: {text}
      </p>
      {band && shared?.length > 0 && <p className="mt-0.5">Shared skills: {shared.join(', ')}</p>}
      {band && <p className="mt-0.5">Based on how closely their skills match this gig.</p>}
    </div>
  )
}

/**
 * One applicant on the client's page. The buttons are exactly the moves the server says are
 * allowed (allowed_next_statuses); nothing about the rules is worked out here.
 */
export default function ApplicantCard({ application, onChangeStatus }) {
  const [pending, setPending] = useState(null) // a status waiting for confirmation
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const { applicant } = application

  const run = async (status, withNote) => {
    setBusy(true)
    setError('')
    try {
      await onChangeStatus(application, status, withNote)
      setPending(null)
      setNote('')
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not change this application. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const choose = (status) => {
    setError('')
    if (CONFIRMED_ACTIONS.includes(status)) setPending(status)
    else run(status)
  }

  return (
    <li className="bg-surface rounded-xl border border-border p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2">
            <Link to={`/profile/${applicant.id}`} className="text-section-title text-primary hover:underline">
              {applicant.full_name}
            </Link>
            {applicant.verified && (
              <span className="inline-flex items-center gap-1 text-caption font-medium text-accent">
                <BadgeCheck size={16} aria-hidden="true" />
                Verified
              </span>
            )}
          </div>
          <p className="text-caption text-muted">
            Applied {formatDateTime(application.created_at)}
            {application.proposed_rate &&
              ` · Proposes KES ${Number(application.proposed_rate).toLocaleString('en-US')}`}
          </p>
        </div>
        <StatusBadge status={application.status} />
      </div>

      {applicant.skills.length > 0 && (
        <ul className="flex flex-wrap gap-2 mb-4" aria-label="Skills">
          {applicant.skills.map((skill) => (
            <li key={skill.id} className="text-caption font-medium px-3 py-1.5 rounded-full bg-primary-light text-primary">
              {skill.name}
            </li>
          ))}
        </ul>
      )}

      <div className="mb-4">
        <Label>Cover letter</Label>
        <p className="text-body text-ink whitespace-pre-wrap">{application.cover_letter}</p>
      </div>

      {application.portfolio_link && (
        <div className="mb-4">
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

      <SkillMatch application={application} />

      <details className="mb-4">
        <summary className="text-label text-muted cursor-pointer">Status history ({application.events.length})</summary>
        <ol className="mt-2 space-y-1.5">
          {application.events.map((event) => (
            <li key={event.id} className="text-body text-ink">
              {event.from_status ? `${statusLabel(event.from_status)} to ${statusLabel(event.to_status)}` : 'Applied'}
              <span className="text-muted">
                {' '}
                · {formatDateTime(event.created_at)} · {event.changed_by_name}
              </span>
              {event.note && <p className="text-caption text-muted">Note: {event.note}</p>}
            </li>
          ))}
        </ol>
      </details>

      {!pending && application.allowed_next_statuses.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-4 border-t border-border">
          {application.allowed_next_statuses.map((status) => (
            <Button
              key={status}
              variant={status === 'hired' ? 'primary' : 'secondary'}
              className="py-2 px-4"
              disabled={busy}
              onClick={() => choose(status)}
            >
              {ACTION_LABELS[status] ?? statusLabel(status)}
            </Button>
          ))}
        </div>
      )}

      {pending && (
        <div className="pt-4 border-t border-border space-y-3" role="group" aria-label={`Confirm: ${ACTION_LABELS[pending]}`}>
          <p className="text-body text-ink">
            {ACTION_LABELS[pending]} {applicant.full_name}? {CONSEQUENCES[pending]}
          </p>
          <label className="block">
            <Label>Note (optional)</Label>
            <textarea
              rows={2}
              maxLength={500}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="w-full px-4 py-3 border border-border rounded-lg text-body text-ink bg-surface focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            />
          </label>
          <div className="flex gap-3">
            <Button
              variant={pending === 'rejected' ? 'danger' : 'primary'}
              loading={busy}
              onClick={() => run(pending, note.trim())}
            >
              Yes, {ACTION_LABELS[pending].toLowerCase()}
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => setPending(null)}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      <div className="mt-3">
        <Alert type="error">{error}</Alert>
      </div>
    </li>
  )
}
