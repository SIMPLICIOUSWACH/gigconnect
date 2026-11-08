import { useEffect, useRef, useState } from 'react'

const MIN = 1
const MAX = 5
const STEP = 0.5

const control =
  'min-h-[40px] min-w-[40px] px-3 rounded-button bg-white/90 text-ink text-[15px] font-bold hover:bg-white disabled:opacity-40'

// A picture that opens enlarged when clicked. In the enlarged view: zoom with the buttons or the mouse wheel, drag to
// pan, and Esc or Close to go back.
export default function ZoomableImage({ src, alt, className = '' }) {
  const [open, setOpen] = useState(false)
  const [zoom, setZoom] = useState(2)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const drag = useRef(null)
  const closeButton = useRef(null)
  const opener = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    opener.current = document.activeElement
    closeButton.current?.focus()
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      opener.current?.focus?.()
    }
  }, [open])

  const show = () => {
    setZoom(2)
    setPan({ x: 0, y: 0 })
    setOpen(true)
  }

  const zoomBy = (amount) => setZoom((value) => Math.min(MAX, Math.max(MIN, value + amount)))

  const onPointerDown = (e) => {
    drag.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }
  const onPointerMove = (e) => {
    if (drag.current) setPan({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y })
  }
  const onPointerUp = () => {
    drag.current = null
  }

  return (
    <>
      <button type="button" onClick={show} className="block w-full cursor-zoom-in rounded-input" aria-label={`Enlarge: ${alt}`}>
        <img src={src} alt={alt} className={`w-full max-h-[420px] object-contain rounded-input bg-sand ${className}`} />
      </button>

      {open && (
        <div role="dialog" aria-modal="true" aria-label={`Enlarged: ${alt}`} className="fixed inset-0 z-50 bg-ink/90 flex flex-col">
          <div className="flex flex-wrap items-center justify-end gap-2 p-3">
            <span className="mr-auto text-white text-label">Drag to move. Zoom {zoom.toFixed(1)}x</span>
            <button type="button" className={control} onClick={() => zoomBy(-STEP)} disabled={zoom <= MIN} aria-label="Zoom out">
              −
            </button>
            <button type="button" className={control} onClick={() => zoomBy(STEP)} disabled={zoom >= MAX} aria-label="Zoom in">
              +
            </button>
            <button type="button" className={control} onClick={() => setPan({ x: 0, y: 0 })}>
              Centre
            </button>
            <button ref={closeButton} type="button" className={control} onClick={() => setOpen(false)}>
              Close
            </button>
          </div>
          <div
            className="flex-1 overflow-hidden flex items-center justify-center cursor-grab active:cursor-grabbing touch-none"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
            onWheel={(e) => zoomBy(e.deltaY < 0 ? STEP : -STEP)}
          >
            <img
              src={src}
              alt={alt}
              draggable={false}
              style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
              className="max-w-[90vw] max-h-[80vh] object-contain select-none"
            />
          </div>
        </div>
      )}
    </>
  )
}
