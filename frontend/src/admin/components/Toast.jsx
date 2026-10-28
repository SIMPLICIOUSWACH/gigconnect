import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'

export const TOAST_MS = 4000

const ToastContext = createContext(() => {})

// One short message at a time, read out by screen readers through the role="status" region.
export function ToastProvider({ children }) {
  const [message, setMessage] = useState('')
  const timer = useRef(null)

  const show = useCallback((text) => {
    clearTimeout(timer.current)
    setMessage(text)
    timer.current = setTimeout(() => setMessage(''), TOAST_MS)
  }, [])

  useEffect(() => () => clearTimeout(timer.current), [])

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div role="status" aria-live="polite" className="fixed bottom-4 inset-x-4 sm:inset-x-auto sm:right-6 z-50 flex justify-center">
        {message && (
          <p className="bg-ink text-white text-body font-medium rounded-button px-5 py-3 shadow-float max-w-md">{message}</p>
        )}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
