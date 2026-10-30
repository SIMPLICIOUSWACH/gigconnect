import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  announceNotificationsChanged,
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../api/notifications'
import Alert from '../components/Alert'
import Button from '../components/Button'
import { formatDateTime } from '../utils/applicationStatus'

const PAGE_SIZE = 20
const pill = (active) =>
  `min-h-[40px] px-4 rounded-pill text-nav ${active ? 'bg-ink text-white font-semibold' : 'bg-surface text-ink-soft shadow-ring-border hover:bg-sand'}`

export default function NotificationsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [page, setPage] = useState(1)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(0)
  const navigate = useNavigate()

  useEffect(() => {
    let alive = true
    setError('')
    fetchNotifications({ page, page_size: PAGE_SIZE, ...(unreadOnly ? { unread: true } : {}) })
      .then((data) => alive && setResult(data))
      .catch(() => alive && setError('Could not load your notifications.'))
    return () => {
      alive = false
    }
  }, [page, unreadOnly, tick])

  const show = (next) => {
    setUnreadOnly(next)
    setPage(1)
    setResult(null)
  }

  const open = async (item) => {
    if (!item.is_read) {
      try {
        await markNotificationRead(item.id)
        announceNotificationsChanged()
      } catch {
        // Failing to mark it read should never stop someone opening it.
      }
    }
    if (item.link) navigate(item.link)
    else setTick((n) => n + 1)
  }

  const markAll = async () => {
    try {
      await markAllNotificationsRead()
      announceNotificationsChanged()
      setPage(1)
      setTick((n) => n + 1)
    } catch {
      setError('Could not mark your notifications as read.')
    }
  }

  const items = result?.results

  return (
    <div className="max-w-[760px]">
      <h1 className="text-page-title text-ink mb-5">Notifications</h1>

      <div className="flex flex-wrap items-center gap-2 mb-5">
        <button type="button" aria-pressed={!unreadOnly} onClick={() => show(false)} className={pill(!unreadOnly)}>
          All
        </button>
        <button type="button" aria-pressed={unreadOnly} onClick={() => show(true)} className={pill(unreadOnly)}>
          Unread
        </button>
        <button type="button" onClick={markAll} className="ml-auto text-label text-primary hover:underline min-h-[40px]">
          Mark all as read
        </button>
      </div>

      {error && (
        <div className="mb-4">
          <Alert type="error">{error}</Alert>
        </div>
      )}

      {!result && !error && (
        <ul aria-label="Loading notifications" className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <li key={i} aria-hidden="true" className="h-20 rounded-tile bg-track animate-pulse" />
          ))}
        </ul>
      )}

      {items?.length === 0 && (
        <div className="text-center py-14 px-4 border border-dashed border-divider rounded-card">
          <p className="text-section-title text-ink">{unreadOnly ? 'No unread notifications' : 'No notifications yet'}</p>
          <p className="text-body text-muted mt-1">
            You choose what you hear about in{' '}
            <Link to="/settings/notifications" className="text-primary font-semibold hover:underline">
              notification settings
            </Link>
            .
          </p>
        </div>
      )}

      {items?.length > 0 && (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => open(item)}
                className="w-full text-left bg-surface rounded-tile shadow-hairline hover:shadow-raised p-4 flex gap-3"
              >
                <span
                  aria-hidden="true"
                  className={`mt-2 w-2 h-2 rounded-full shrink-0 ${item.is_read ? 'bg-transparent' : 'bg-coral-deep'}`}
                />
                <span className="min-w-0">
                  {!item.is_read && <span className="sr-only">Unread: </span>}
                  <span className={`block text-body text-ink break-words ${item.is_read ? '' : 'font-semibold'}`}>{item.title}</span>
                  <span className="block text-body text-ink-soft break-words mt-0.5">{item.body}</span>
                  <span className="block text-caption text-muted mt-1">{formatDateTime(item.created_at)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {result?.total_pages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <Button variant="secondary" disabled={!result.previous} onClick={() => setPage(page - 1)}>
            Previous
          </Button>
          <span className="text-body text-muted">
            Page {result.page} of {result.total_pages}
          </span>
          <Button variant="secondary" disabled={!result.next} onClick={() => setPage(page + 1)}>
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
