import { useEffect, useId, useRef } from 'react'

const FOCUSABLE =
  'button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'

/*
  A modal dialog. Focus moves into it and stays there (Tab wraps around), Esc or a click outside closes it unless
  `busy`, and focus goes back to whatever opened it.
*/
export default function Modal({ title, description, onClose, busy = false, children, wide = false }) {
  const panel = useRef(null)
  const opener = useRef(null)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    opener.current = document.activeElement
    panel.current?.querySelector(FOCUSABLE)?.focus()
    return () => opener.current?.focus?.()
  }, [])

  const close = () => {
    if (!busy) onClose()
  }

  const onKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.stopPropagation()
      close()
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink/50" aria-hidden="true" onClick={close} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        onKeyDown={onKeyDown}
        className={`relative w-full ${wide ? 'max-w-xl' : 'max-w-md'} max-h-[calc(100dvh-32px)] overflow-y-auto bg-surface rounded-card shadow-float p-6`}
      >
        <h2 id={titleId} className="text-section-title text-ink">
          {title}
        </h2>
        {description && (
          <p id={descriptionId} className="text-body text-ink-soft mt-2">
            {description}
          </p>
        )}
        {children}
      </div>
    </div>
  )
}
