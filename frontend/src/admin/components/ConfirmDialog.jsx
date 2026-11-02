import { useEffect, useId, useRef, useState } from 'react'

const FOCUSABLE = 'button:not([disabled]), textarea:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'

/*
  The confirmation step for admin actions. A modal dialog: focus moves into it and stays there (Tab wraps around),
  Esc or Cancel closes it, and focus goes back to whatever opened it. The reason is required unless
  `reasonRequired` is false; the person affected is shown what it says.
*/
export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  reasonLabel = 'Reason',
  reasonHint = 'The person affected sees this.',
  reasonRequired = true,
  onConfirm,
  onCancel,
}) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const panel = useRef(null)
  const textarea = useRef(null)
  const opener = useRef(null)
  const titleId = useId()
  const descriptionId = useId()
  const reasonId = useId()
  const hintId = useId()

  useEffect(() => {
    if (!open) return undefined
    opener.current = document.activeElement
    setReason('')
    setError('')
    setBusy(false)
    textarea.current?.focus()
    return () => opener.current?.focus?.()
  }, [open])

  if (!open) return null

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
    const text = reason.trim()
    if (reasonRequired && !text) {
      setError('Give a reason before you confirm.')
      textarea.current?.focus()
      return
    }
    setBusy(true)
    setError('')
    try {
      await onConfirm(text)
    } catch (err) {
      setError(err?.message || 'That did not work. Try again.')
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink/50" aria-hidden="true" onClick={cancel} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        onKeyDown={onKeyDown}
        className="relative w-full max-w-md bg-surface rounded-card shadow-float p-6"
      >
        <h2 id={titleId} className="text-section-title text-ink">
          {title}
        </h2>
        {description && (
          <p id={descriptionId} className="text-body text-ink-soft mt-2">
            {description}
          </p>
        )}
        <form onSubmit={submit} className="mt-5" noValidate>
          <label htmlFor={reasonId} className="block text-label text-ink">
            {reasonLabel}
            {reasonRequired ? <span className="text-coral-ink"> *</span> : <span className="text-muted font-normal"> (optional)</span>}
          </label>
          <p id={hintId} className="text-caption text-muted mt-0.5">
            {reasonHint}
          </p>
          <textarea
            ref={textarea}
            id={reasonId}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required={reasonRequired}
            aria-required={reasonRequired}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? `${hintId} ${reasonId}-error` : hintId}
            maxLength={1000}
            rows={4}
            className="mt-2 w-full rounded-input border border-border bg-surface px-3 py-2.5 text-body text-ink focus:outline-none focus:ring-2 focus:ring-primary"
          />
          {error && (
            <p id={`${reasonId}-error`} role="alert" className="text-caption text-coral-ink mt-1">
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
              disabled={busy}
              className="min-h-[44px] px-5 rounded-button bg-coral-dark text-white text-[15px] font-bold hover:bg-ink disabled:opacity-60"
            >
              {busy ? 'Working…' : confirmLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
