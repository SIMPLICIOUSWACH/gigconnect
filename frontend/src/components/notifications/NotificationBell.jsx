import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'
import {
  announceNotificationsChanged,
  fetchNotifications,
  fetchUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
  onNotificationsChanged,
} from '../../api/notifications'
import { formatDateTime } from '../../utils/applicationStatus'

export const POLL_MS = 30000
const LATEST = 6

// The bell in the header. It asks for the unread count every 30 seconds while the tab is showing, and again as soon as
// the tab comes back into view, so a new notification appears within half a minute without a page reload.
export default function NotificationBell() {
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState(null)
  const [error, setError] = useState(false)
  const ref = useRef(null)
  const navigate = useNavigate()

  const refreshCount = useCallback(() => {
    if (document.hidden) return
    fetchUnreadCount().then(setUnread).catch(() => {})
  }, [])

  useEffect(() => {
    refreshCount()
    const timer = setInterval(refreshCount, POLL_MS)
    document.addEventListener('visibilitychange', refreshCount)
    const stopListening = onNotificationsChanged(refreshCount)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', refreshCount)
      stopListening()
    }
  }, [refreshCount])

  useEffect(() => {
    if (!open) return undefined
    let alive = true
    setItems(null)
    setError(false)
    fetchNotifications({ page_size: LATEST })
      .then((data) => alive && setItems(data.results))
      .catch(() => alive && setError(true))
    const close = (e) => {
      if (e.type === 'keydown' ? e.key === 'Escape' : !ref.current?.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      alive = false
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  const openItem = (item) => {
    setOpen(false)
    if (!item.is_read) {
      markNotificationRead(item.id).then(announceNotificationsChanged).catch(() => {})
    }
    if (item.link) navigate(item.link)
  }

  const markAll = async () => {
    try {
      await markAllNotificationsRead()
      setItems((current) => current?.map((item) => ({ ...item, is_read: true })))
      setUnread(0)
      announceNotificationsChanged()
    } catch {
      setError(true)
    }
  }

  const label = unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="relative w-11 h-11 rounded-full flex items-center justify-center text-ink-soft hover:bg-sand hover:text-ink"
      >
        <Bell size={22} aria-hidden="true" />
        {unread > 0 && (
          <span
            aria-hidden="true"
            className="absolute top-0.5 right-0.5 min-w-[20px] h-5 px-1 rounded-pill bg-coral-deep text-white text-badge flex items-center justify-center"
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <section
          aria-label="Latest notifications"
          className="fixed inset-x-4 top-[72px] sm:absolute sm:inset-x-auto sm:top-auto sm:right-0 sm:mt-2 sm:w-[360px] bg-surface rounded-tile shadow-raised z-40 overflow-hidden"
        >
          <div className="flex items-center justify-between gap-3 px-4 pt-4 pb-2">
            <h2 className="text-label text-ink">Notifications</h2>
            {unread > 0 && (
              <button type="button" onClick={markAll} className="text-caption font-semibold text-primary hover:underline">
                Mark all as read
              </button>
            )}
          </div>

          {error && <p className="px-4 py-3 text-body text-coral-ink">Could not load your notifications.</p>}
          {!error && items === null && <p className="px-4 py-3 text-body text-muted">Loading…</p>}
          {!error && items?.length === 0 && <p className="px-4 py-3 text-body text-muted">Nothing here yet.</p>}

          {items?.length > 0 && (
            <ul className="divide-y divide-line max-h-[380px] overflow-y-auto">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => openItem(item)}
                    className="w-full text-left px-4 py-3 hover:bg-sand flex gap-3"
                  >
                    <span
                      aria-hidden="true"
                      className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${item.is_read ? 'bg-transparent' : 'bg-coral-deep'}`}
                    />
                    <span className="min-w-0">
                      {!item.is_read && <span className="sr-only">Unread: </span>}
                      <span className={`block text-[14px] leading-5 text-ink break-words ${item.is_read ? '' : 'font-semibold'}`}>
                        {item.title}
                      </span>
                      <span className="block text-caption text-muted mt-0.5">{formatDateTime(item.created_at)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <Link
            to="/notifications"
            onClick={() => setOpen(false)}
            className="block px-4 py-3 border-t border-line text-center text-label text-primary hover:bg-sand"
          >
            See all notifications
          </Link>
        </section>
      )}
    </div>
  )
}
