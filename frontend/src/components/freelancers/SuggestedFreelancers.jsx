import { useEffect, useId, useState } from 'react'
import { fetchSuggestedFreelancers, inviteError, inviteToApply } from '../../api/freelancers'
import FreelancerCard from './FreelancerCard'

const pill = 'inline-flex items-center justify-center min-h-[40px] px-4 rounded-button text-[14px] font-bold'

function InviteButton({ freelancer, invited, busy, onInvite }) {
  if (invited) {
    return <span className={`${pill} bg-accent-light text-accent`}>Invited</span>
  }
  return (
    <button
      type="button"
      onClick={onInvite}
      disabled={busy}
      className={`${pill} bg-primary text-white hover:bg-primary-hover disabled:opacity-60`}
    >
      {busy ? 'Inviting…' : 'Invite to apply'}
      <span className="sr-only"> {freelancer.full_name}</span>
    </button>
  )
}

function Suggestions({ gigId, headingId }) {
  const [data, setData] = useState(null)
  const [loadError, setLoadError] = useState(false)
  const [busyId, setBusyId] = useState(null)
  const [message, setMessage] = useState(null) // { type: 'ok' | 'error', text }

  useEffect(() => {
    let alive = true
    fetchSuggestedFreelancers(gigId)
      .then((result) => alive && setData(result))
      .catch(() => alive && setLoadError(true))
    return () => {
      alive = false
    }
  }, [gigId])

  const invite = async (freelancer) => {
    setBusyId(freelancer.id)
    setMessage(null)
    try {
      const result = await inviteToApply(gigId, freelancer.id)
      setData((current) => ({
        ...current,
        results: current.results.map((row) => (row.id === freelancer.id ? { ...row, invited: true } : row)),
      }))
      setMessage({ type: 'ok', text: result.detail })
    } catch (err) {
      setMessage({ type: 'error', text: inviteError(err) })
    } finally {
      setBusyId(null)
    }
  }

  if (loadError) return <p className="text-body text-coral-ink">Could not load suggestions.</p>
  if (!data) {
    return (
      <ul aria-label="Loading suggestions" className="grid gap-4 sm:grid-cols-2">
        {[0, 1].map((i) => (
          <li key={i} aria-hidden="true" className="h-48 rounded-card bg-track animate-pulse" />
        ))}
      </ul>
    )
  }
  if (!data.suggestions.available) {
    return (
      <p className="text-body text-muted">
        {data.suggestions.reason === 'gig_not_open'
          ? 'Suggestions are for open gigs.'
          : 'Suggestions are not available right now.'}
      </p>
    )
  }
  if (data.results.length === 0) {
    return (
      <p className="text-body text-muted">
        No freelancers share this gig&apos;s skills yet, apart from anyone who has already applied.
      </p>
    )
  }

  return (
    <>
      {message && (
        <p
          role={message.type === 'error' ? 'alert' : 'status'}
          className={`mb-3 rounded-input px-4 py-2.5 text-[14px] font-semibold ${
            message.type === 'error' ? 'bg-coral-light text-coral-ink' : 'bg-accent-light text-accent'
          }`}
        >
          {message.text}
        </p>
      )}
      <ul aria-labelledby={headingId} className="grid gap-4 sm:grid-cols-2">
        {data.results.map((freelancer) => (
          <li key={freelancer.id}>
            <FreelancerCard
              freelancer={freelancer}
              action={
                <InviteButton
                  freelancer={freelancer}
                  invited={freelancer.invited}
                  busy={busyId === freelancer.id}
                  onInvite={() => invite(freelancer)}
                />
              }
            />
          </li>
        ))}
      </ul>
    </>
  )
}

/*
  "Suggested for this gig": up to 6 freelancers whose skills and profile best match one of the client's open gigs,
  with the same skill-overlap labels as applicant cards. People who already applied aren't listed.

  In My gigs it starts closed (`collapsed`) and only asks the server when opened, so a client with many open gigs
  doesn't fire a request for each. On the gig page it is open from the start.
*/
export default function SuggestedFreelancers({ gigId, collapsed = false }) {
  const [open, setOpen] = useState(!collapsed)
  const headingId = useId()
  const panelId = useId()

  if (collapsed) {
    return (
      <div className="mt-4">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((value) => !value)}
          className="text-body text-primary font-medium hover:underline"
        >
          <span id={headingId}>Suggested freelancers for this gig</span>
          <span aria-hidden="true"> {open ? '▴' : '▾'}</span>
        </button>
        <div id={panelId} className="mt-3" hidden={!open}>
          {open && <Suggestions gigId={gigId} headingId={headingId} />}
        </div>
      </div>
    )
  }

  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId} className="text-section-title text-ink">
        Suggested for this gig
      </h2>
      <p className="text-body text-muted mt-1 mb-4">
        Freelancers whose skills match this gig. Invite one to apply and they&apos;ll get a notification.
      </p>
      <Suggestions gigId={gigId} headingId={headingId} />
    </section>
  )
}
