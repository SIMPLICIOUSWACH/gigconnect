import { useCallback, useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { fetchMessageUnreadCount, onMessagesChanged } from '../../api/messages'

export const BADGE_POLL_MS = 30000

// "Messages" in the main navigation, with the number of unread messages. Checked every 30 seconds while the tab is
// showing, when the tab comes back into view, and as soon as an open chat is read.
export default function MessagesNavLink({ className }) {
  const [unread, setUnread] = useState(0)

  const refresh = useCallback(() => {
    if (document.hidden) return
    fetchMessageUnreadCount().then(setUnread).catch(() => {})
  }, [])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, BADGE_POLL_MS)
    document.addEventListener('visibilitychange', refresh)
    const stop = onMessagesChanged(refresh)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', refresh)
      stop()
    }
  }, [refresh])

  return (
    <NavLink to="/messages" className={(state) => `${className(state)} inline-flex items-center gap-2`}>
      Messages
      {unread > 0 && (
        <span className="min-w-[20px] h-5 px-1.5 rounded-pill bg-coral-deep text-white text-badge flex items-center justify-center">
          {unread > 99 ? '99+' : unread}
          <span className="sr-only"> unread</span>
        </span>
      )}
    </NavLink>
  )
}
