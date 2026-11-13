import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchInvitableGigs, inviteError, inviteToApply } from '../../api/freelancers'
import Button from '../Button'
import Modal from '../Modal'

/*
  "Invite to apply": the client picks one of their open gigs and the freelancer gets a notification with its link.
  Gigs the freelancer was already invited to, or has applied to, can't be picked. Inviting doesn't open a chat.
*/
export default function InviteDialog({ freelancer, onInvited, onClose }) {
  const [data, setData] = useState(null)
  const [loadError, setLoadError] = useState(false)
  const [gigId, setGigId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    fetchInvitableGigs(freelancer.id)
      .then((result) => {
        if (!alive) return
        setData(result)
        const first = result.gigs.find((gig) => !gig.invited && !gig.applied)
        setGigId(first?.id || '')
      })
      .catch(() => alive && setLoadError(true))
    return () => {
      alive = false
    }
  }, [freelancer.id])

  const submit = async (e) => {
    e.preventDefault()
    if (!gigId) return
    setBusy(true)
    setError('')
    try {
      const result = await inviteToApply(gigId, freelancer.id)
      onInvited(result)
    } catch (err) {
      setError(inviteError(err))
      setBusy(false)
    }
  }

  const gigs = data?.gigs || []
  const noneLeft = data && data.invites_left <= 0

  return (
    <Modal
      title={`Invite ${freelancer.full_name} to apply`}
      description="They get a notification with a link to the gig. It's up to them whether to apply."
      onClose={onClose}
      busy={busy}
      wide
    >
      {loadError && (
        <p role="alert" className="mt-4 text-body text-coral-ink">
          Could not load your gigs.
        </p>
      )}
      {!data && !loadError && (
        <div aria-label="Loading your open gigs" className="mt-4 space-y-2">
          <div className="h-11 rounded-input bg-track animate-pulse" />
          <div className="h-11 rounded-input bg-track animate-pulse" />
        </div>
      )}

      {data && gigs.length === 0 && (
        <div className="mt-4">
          <p className="text-body text-ink-soft">You have no open gigs to invite them to.</p>
          <Link to="/gigs/new" className="inline-block mt-2 text-label text-primary hover:underline">
            Post a gig
          </Link>
        </div>
      )}

      {data && gigs.length > 0 && (
        <form onSubmit={submit} className="mt-4" noValidate>
          <fieldset>
            <legend className="text-label text-ink mb-2">Which gig?</legend>
            <ul className="space-y-2 max-h-[280px] overflow-y-auto">
              {gigs.map((gig) => {
                const taken = gig.invited || gig.applied
                return (
                  <li key={gig.id}>
                    <label
                      className={`flex items-center gap-3 rounded-input border px-3 py-2.5 ${
                        taken ? 'border-line bg-sand text-muted' : 'border-border cursor-pointer hover:bg-sand'
                      } ${gigId === gig.id ? 'border-primary ring-1 ring-primary' : ''}`}
                    >
                      <input
                        type="radio"
                        name="invite-gig"
                        value={gig.id}
                        checked={gigId === gig.id}
                        disabled={taken || busy}
                        onChange={() => setGigId(gig.id)}
                        className="w-4 h-4 accent-primary"
                      />
                      <span className="min-w-0 flex-1 text-body truncate">{gig.title}</span>
                      {gig.applied && <span className="text-caption font-semibold shrink-0">Already applied</span>}
                      {!gig.applied && gig.invited && <span className="text-caption font-semibold shrink-0">Already invited</span>}
                    </label>
                  </li>
                )
              })}
            </ul>
          </fieldset>

          <p className="text-caption text-muted mt-3">
            {noneLeft
              ? 'You have used all your invitations for today. Try again tomorrow.'
              : `You can send ${data.invites_left} more ${data.invites_left === 1 ? 'invitation' : 'invitations'} today.`}
          </p>
          {error && (
            <p role="alert" className="text-caption text-coral-ink mt-2">
              {error}
            </p>
          )}

          <div className="mt-5 flex flex-wrap justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" loading={busy} disabled={!gigId || noneLeft}>
              Send invitation
            </Button>
          </div>
        </form>
      )}

      {(loadError || (data && gigs.length === 0)) && (
        <div className="mt-5 flex justify-end">
          <Button type="button" variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      )}
    </Modal>
  )
}
