import { Link } from 'react-router-dom'
import { initials } from '../../utils/palette'
import { shortWhen } from './chatFormat'

function preview(conversation) {
  const last = conversation.last_message
  if (!last) {
    if (conversation.waiting_for_client && conversation.my_role === 'freelancer') return 'Waiting for the client to write'
    return conversation.my_role === 'client' ? 'Send the first message' : 'No messages yet'
  }
  return last.from_me ? `You: ${last.body}` : last.body
}

export function ConversationListSkeleton() {
  return (
    <ul aria-label="Loading your chats" className="p-2 space-y-1">
      {Array.from({ length: 4 }).map((_, i) => (
        <li key={i} aria-hidden="true" className="flex gap-3 items-center p-3">
          <span className="w-11 h-11 rounded-full bg-track animate-pulse shrink-0" />
          <span className="flex-1 space-y-2">
            <span className="block h-3.5 w-1/2 rounded bg-track animate-pulse" />
            <span className="block h-3 w-4/5 rounded bg-track animate-pulse" />
          </span>
        </li>
      ))}
    </ul>
  )
}

export default function ConversationList({ conversations, activeId, role }) {
  if (conversations.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center px-6 py-14">
        <p className="text-section-title text-ink">No messages yet</p>
        <p className="text-body text-muted mt-1 max-w-xs">
          {role === 'client'
            ? 'When you hire a freelancer, you can message them here.'
            : 'When a client hires you, your chat with them appears here.'}
        </p>
      </div>
    )
  }

  return (
    <ul className="p-2 space-y-1">
      {conversations.map((conversation) => {
        const active = conversation.id === activeId
        const unread = conversation.unread_count
        const name = conversation.other.full_name
        return (
          <li key={conversation.id}>
            <Link
              to={`/messages/${conversation.id}`}
              aria-current={active ? 'page' : undefined}
              className={`flex gap-3 items-center p-3 rounded-tile ${active ? 'bg-primary-light' : 'hover:bg-sand'}`}
            >
              <span
                aria-hidden="true"
                className="w-11 h-11 shrink-0 rounded-full bg-primary-light text-primary font-bold text-[15px] flex items-center justify-center ring-2 ring-surface"
              >
                {initials(name)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline gap-2">
                  <span className={`truncate text-[15px] leading-5 text-ink ${unread ? 'font-bold' : 'font-semibold'}`}>
                    {name}
                  </span>
                  <span className="ml-auto shrink-0 text-[12px] leading-4 text-muted">
                    {shortWhen(conversation.last_message_at || conversation.hired_at)}
                  </span>
                </span>
                <span className="block truncate text-caption text-muted">{conversation.gig.title}</span>
                <span className="flex items-center gap-2">
                  <span className={`truncate text-caption ${unread ? 'text-ink font-semibold' : 'text-ink-soft'}`}>
                    {preview(conversation)}
                  </span>
                  {unread > 0 && (
                    <span className="ml-auto shrink-0 min-w-[20px] h-5 px-1.5 rounded-pill bg-coral-deep text-white text-badge flex items-center justify-center">
                      {unread}
                      <span className="sr-only"> unread</span>
                    </span>
                  )}
                </span>
              </span>
            </Link>
          </li>
        )
      })}
    </ul>
  )
}
