import { useCallback, useEffect, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { fetchConversations } from '../api/messages'
import Alert from '../components/Alert'
import ChatThread from '../components/messages/ChatThread'
import ConversationList, { ConversationListSkeleton } from '../components/messages/ConversationList'
import { useAuth } from '../context/AuthContext'

export const LIST_POLL_MS = 15000

/*
  /messages and /messages/:id. On wide screens the chat list and the open chat sit side by side; on phones the list
  and the chat are separate screens, and the chat has a back button.
*/
export default function MessagesPage() {
  const { id } = useParams()
  const location = useLocation()
  const { user } = useAuth()
  const [conversations, setConversations] = useState(null)
  const [error, setError] = useState('')

  const refresh = useCallback(() => {
    if (document.hidden) return
    fetchConversations({ page_size: 50 })
      .then((data) => {
        setConversations(data.results)
        setError('')
      })
      .catch(() => setError('Could not load your chats.'))
  }, [])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, LIST_POLL_MS)
    return () => clearInterval(timer)
  }, [refresh])

  return (
    <div>
      <h1 className={`text-page-title text-ink mb-5 ${id ? 'hidden md:block' : ''}`}>Messages</h1>
      {error && (
        <div className="mb-4">
          <Alert type="error">{error}</Alert>
        </div>
      )}
      <div className="bg-surface rounded-card shadow-raised overflow-hidden md:grid md:grid-cols-[340px_minmax(0,1fr)] h-[calc(100dvh-210px)] md:h-[calc(100dvh-190px)] min-h-[420px]">
        <section
          aria-label="Your chats"
          className={`${id ? 'hidden md:block' : 'block'} h-full overflow-y-auto md:border-r md:border-line`}
        >
          {conversations === null ? (
            <ConversationListSkeleton />
          ) : (
            <ConversationList conversations={conversations} activeId={id} role={user?.role} />
          )}
        </section>
        <section aria-label="Chat" className={`${id ? 'block' : 'hidden md:block'} h-full min-h-0`}>
          {id ? (
            <ChatThread key={id} id={id} initialDraft={location.state?.draft || ''} onActivity={refresh} />
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center px-6">
              <p className="text-section-title text-ink">Choose a chat</p>
              <p className="text-body text-muted mt-1">Your messages with the people you work with appear here.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
