import { useEffect, useId, useRef, useState } from 'react'
import { errorMessage, deleteUser, fetchDeletePreview } from '../api'

const FOCUSABLE = 'button:not([disabled]), textarea:not([disabled]), input:not([disabled]), [href]'

const plural = (count, one, many = `${one}s`) => `${count} ${count === 1 ? one : many}`

// The preview as sentences, leaving out what doesn't apply to this account.
export function previewLines(preview, force) {
  const lines = []
  if (force && preview.active_work.length) {
    lines.push(`${plural(preview.active_work.length, 'in-progress gig')} will be closed, and the other person told.`)
  }
  if (preview.open_gigs_closed) {
    lines.push(
      `${plural(preview.open_gigs_closed, 'open gig')} will be closed` +
        (preview.applicants_notified ? `, and ${plural(preview.applicants_notified, 'waiting freelancer')} told.` : '.')
    )
  }
  if (preview.applications_emptied) {
    lines.push(`${plural(preview.applications_emptied, 'application')} will be emptied, and open ones withdrawn.`)
  }
  if (preview.id_files_deleted || preview.id_number_deleted) {
    lines.push('ID documents, selfie and ID number deleted. Only the keyed hash stays, so the ID can’t be reused.')
  }
  if (preview.conversations_read_only) {
    lines.push(`${plural(preview.conversations_read_only, 'chat')} kept for the other person, read-only, shown as "Deleted user".`)
  }
  if (preview.notifications_deleted || preview.gig_history_deleted) {
    lines.push(
      `${plural(preview.notifications_deleted, 'notification')} and ${plural(preview.gig_history_deleted, 'gig view')} deleted.`
    )
  }
  lines.push('Name, email and phone erased, and signed out everywhere.')
  lines.push('They are emailed that an administrator deleted the account, with your reason.')
  return lines
}

/*
  Deleting an account for good. It shows what will happen first (from the preview endpoint), then asks for a reason
  and for the account's email typed out exactly. Confirm stays disabled until all of that is right, and until the
  admin has ticked the box if there is work in progress.
*/
export default function DeleteUserDialog({ user, onDeleted, onCancel }) {
  const [preview, setPreview] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [reason, setReason] = useState('')
  const [typed, setTyped] = useState('')
  const [force, setForce] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const panel = useRef(null)
  const opener = useRef(null)
  const titleId = useId()
  const reasonId = useId()
  const emailId = useId()
  const forceId = useId()

  useEffect(() => {
    opener.current = document.activeElement
    let alive = true
    fetchDeletePreview(user.id)
      .then((data) => alive && setPreview(data))
      .catch((err) => alive && setLoadError(errorMessage(err, 'Could not load what deleting would do.')))
    return () => {
      alive = false
      opener.current?.focus?.()
    }
  }, [user.id])

  useEffect(() => {
    if (preview) panel.current?.querySelector('textarea')?.focus()
  }, [preview])

  const activeWork = preview?.active_work || []
  const ready =
    Boolean(preview?.can_delete) && reason.trim() !== '' && typed === user.email && (activeWork.length === 0 || force)

  const cancel = () => {
    if (!busy) onCancel()
  }

  const onKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.stopPropagation()
      cancel()
      return
    }
    if (e.key !== 'Tab') return
    const items = [...panel.current.querySelectorAll(FOCUSABLE)]
    if (items.length === 0) return
    const first = items[0]
    const last = items[items.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!ready) return
    setBusy(true)
    setError('')
    try {
      const result = await deleteUser(user.id, { reason: reason.trim(), confirm_email: typed, force })
      onDeleted(result.summary)
    } catch (err) {
      const data = err?.response?.data
      if (data?.code === 'active_work') setPreview((current) => ({ ...current, active_work: data.active_work }))
      setError(errorMessage(err, 'Could not delete this account.'))
      setBusy(false)
    }
  }

  const field =
    'mt-2 w-full rounded-input border border-border bg-surface px-3 py-2.5 text-body text-ink focus:outline-none focus:ring-2 focus:ring-primary'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink/50" aria-hidden="true" onClick={cancel} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={onKeyDown}
        className="relative w-full max-w-lg max-h-[calc(100dvh-32px)] overflow-y-auto bg-surface rounded-card shadow-float p-6"
      >
        <h2 id={titleId} className="text-section-title text-ink">
          Delete this account permanently?
        </h2>
        <p className="text-body text-ink-soft mt-2">
          {user.full_name}&apos;s personal data is erased and the account can&apos;t be recovered.
        </p>

        {loadError && (
          <p role="alert" className="mt-4 rounded-input bg-coral-light text-coral-ink px-4 py-3 text-body">
            {loadError}
          </p>
        )}
        {!preview && !loadError && (
          <div aria-label="Loading what will happen" className="mt-4 space-y-2">
            <div className="h-4 w-4/5 rounded bg-track animate-pulse" />
            <div className="h-4 w-3/5 rounded bg-track animate-pulse" />
          </div>
        )}
        {preview && !preview.can_delete && (
          <p role="alert" className="mt-4 rounded-input bg-coral-light text-coral-ink px-4 py-3 text-body">
            {preview.refusal}
          </p>
        )}

        {preview?.can_delete && (
          <form onSubmit={submit} className="mt-4" noValidate>
            {activeWork.length > 0 && (
              <div className="rounded-input bg-sun-light text-sun-deep px-4 py-3 mb-4">
                <p className="text-label">Work in progress</p>
                <ul aria-label="Work in progress" className="mt-1 space-y-0.5 text-[14px] leading-5">
                  {activeWork.map((item) => (
                    <li key={item.gig_id}>
                      &quot;{item.title}&quot; ({item.as === 'client' ? 'their gig' : 'they were hired'}
                      {item.other_party ? `, with ${item.other_party}` : ''})
                    </li>
                  ))}
                </ul>
                <div className="flex items-start gap-2 mt-3">
                  <input
                    id={forceId}
                    type="checkbox"
                    checked={force}
                    onChange={(e) => setForce(e.target.checked)}
                    className="mt-1 w-4 h-4 accent-coral-dark"
                  />
                  <label htmlFor={forceId} className="text-[14px] leading-5 font-semibold">
                    I understand: close these gigs/contracts
                  </label>
                </div>
              </div>
            )}

            <p className="text-label text-ink">What will happen</p>
            <ul className="mt-1 mb-5 list-disc pl-5 space-y-1 text-[14px] leading-5 text-ink-soft">
              {previewLines(preview, force).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>

            <label htmlFor={reasonId} className="block text-label text-ink">
              Reason<span className="text-coral-ink"> *</span>
            </label>
            <p className="text-caption text-muted mt-0.5">Saved in the audit log and emailed to them.</p>
            <textarea
              id={reasonId}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
              aria-required="true"
              maxLength={1000}
              rows={3}
              className={field}
            />

            <label htmlFor={emailId} className="block text-label text-ink mt-4">
              Type <span className="font-bold break-all">{user.email}</span> to confirm
            </label>
            <input
              id={emailId}
              type="text"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              aria-invalid={typed !== '' && typed !== user.email}
              className={field}
            />

            {error && (
              <p role="alert" className="text-caption text-coral-ink mt-3">
                {error}
              </p>
            )}

            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button
                type="button"
                onClick={cancel}
                disabled={busy}
                className="min-h-[44px] px-5 rounded-button border-2 border-ink text-ink text-[15px] font-bold hover:bg-sand disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!ready || busy}
                className="min-h-[44px] px-5 rounded-button bg-coral-dark text-white text-[15px] font-bold hover:bg-ink disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {busy ? 'Deleting…' : 'Delete account permanently'}
              </button>
            </div>
          </form>
        )}

        {((preview && !preview.can_delete) || loadError) && (
          <div className="mt-6 flex justify-end">
            <button
              type="button"
              onClick={cancel}
              className="min-h-[44px] px-5 rounded-button border-2 border-ink text-ink text-[15px] font-bold hover:bg-sand"
            >
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
