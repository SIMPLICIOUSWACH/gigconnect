import { Fragment, useCallback, useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Flag, Lock, Send, ShieldCheck } from 'lucide-react'
import ConfirmDialog from '../../admin/components/ConfirmDialog'
import {
  MESSAGE_MAX_LENGTH,
  announceMessagesChanged,
  fetchConversation,
  fetchMessages,
  markConversationRead,
  reportConversation,
  sendMessage,
} from '../../api/messages'
import { initials } from '../../utils/palette'
import { dayOf, longDate, timeOf } from './chatFormat'

export const THREAD_POLL_MS = 4000
const DETAIL_EVERY = 8 // polls between checks of the chat itself (read-only, waiting), about every half a minute
const COUNTER_FROM = MESSAGE_MAX_LENGTH - 200

let pendingCount = 0

// Server messages in order, then the ones still being sent (or that failed) in the order they were written.
function ordered(messages) {
  const sent = messages.filter((m) => m.id).sort((a, b) => a.id - b.id)
  return [...sent, ...messages.filter((m) => !m.id)]
}

function merge(current, incoming) {
  const known = new Set(current.filter((m) => m.id).map((m) => m.id))
  const next = [...current]
  for (const message of incoming) {
    if (known.has(message.id)) continue
    if (message.from_me) {
      // A poll can bring back my message before the send call answers: drop the placeholder for it.
      const i = next.findIndex((m) => !m.id && m.status === 'sending' && m.body === message.body)
      if (i >= 0) next.splice(i, 1)
    }
    next.push(message)
    known.add(message.id)
  }
  return ordered(next)
}

const errorText = (err, fallback) => err?.response?.data?.detail || err?.response?.data?.body?.[0] || fallback

export function ThreadSkeleton() {
  return (
    <div aria-label="Loading the chat" className="flex flex-col h-full">
      <div className="h-[76px] border-b border-line px-5 flex items-center gap-3" aria-hidden="true">
        <span className="w-11 h-11 rounded-full bg-track animate-pulse" />
        <span className="h-4 w-40 rounded bg-track animate-pulse" />
      </div>
      <div className="flex-1 p-5 space-y-3" aria-hidden="true">
        <div className="h-12 w-1/2 rounded-tile bg-track animate-pulse" />
        <div className="h-12 w-2/5 rounded-tile bg-track animate-pulse ml-auto" />
        <div className="h-16 w-3/5 rounded-tile bg-track animate-pulse" />
      </div>
    </div>
  )
}

function Avatar({ name }) {
  return (
    <span
      aria-hidden="true"
      className="w-11 h-11 shrink-0 rounded-full bg-primary-light text-primary font-bold text-[15px] flex items-center justify-center"
    >
      {initials(name)}
    </span>
  )
}

function Banner({ icon: Icon, children }) {
  return (
    <div className="mx-4 sm:mx-5 mb-3 flex items-start gap-2.5 rounded-input bg-sand px-4 py-3 text-[14px] leading-5 text-ink-soft">
      <Icon size={18} aria-hidden="true" className="mt-px shrink-0 text-ink-soft" />
      <p>{children}</p>
    </div>
  )
}

/*
  One conversation. It checks for new messages every 4 seconds while the tab is showing, marks the other person's
  messages as read while it is open, and sends optimistically: a message shows at once and gets a Retry button if
  sending fails.
*/
export default function ChatThread({ id, initialDraft = '', onActivity = () => {} }) {
  const [conversation, setConversation] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [messages, setMessages] = useState([])
  const [hasEarlier, setHasEarlier] = useState(false)
  const [seenUpTo, setSeenUpTo] = useState(null)
  const [draft, setDraft] = useState('')
  const [tip, setTip] = useState('')
  const [notice, setNotice] = useState('')
  const [reporting, setReporting] = useState(false)
  const logRef = useRef(null)
  const stickToBottom = useRef(true)
  const lastId = useRef(null)
  const polls = useRef(0)
  // The parent's callback, kept in a ref so a new function each render doesn't restart loading and polling.
  const activity = useRef(onActivity)
  useEffect(() => {
    activity.current = onActivity
  }, [onActivity])
  const tellParent = useCallback(() => activity.current(), [])
  const inputId = useId()
  const counterId = useId()

  const loadConversation = useCallback(
    () =>
      fetchConversation(id)
        .then(setConversation)
        .catch((err) => {
          setLoadError(err?.response?.status === 404 ? 'This chat is not available.' : 'Could not load this chat.')
        }),
    [id]
  )

  const markRead = useCallback(
    (incoming) => {
      if (document.hidden || !incoming.some((m) => !m.from_me && !m.read_at)) return
      markConversationRead(id)
        .then(() => {
          announceMessagesChanged()
          tellParent()
        })
        .catch(() => {})
    },
    [id, tellParent]
  )

  const take = useCallback(
    (data) => {
      if (data.results.length) {
        lastId.current = Math.max(lastId.current || 0, ...data.results.map((m) => m.id))
        setMessages((current) => merge(current, data.results))
      }
      setSeenUpTo(data.seen_up_to)
      markRead(data.results)
      return data
    },
    [markRead]
  )

  // First load.
  useEffect(() => {
    let alive = true
    loadConversation()
    fetchMessages(id)
      .then((data) => {
        if (!alive) return
        setHasEarlier(data.has_earlier)
        take(data)
      })
      .catch(() => alive && setLoadError('Could not load this chat.'))
    return () => {
      alive = false
    }
  }, [id, loadConversation, take])

  // The client's suggested first message, only while the chat is still empty.
  useEffect(() => {
    if (initialDraft && conversation?.my_role === 'client' && !conversation.first_message_at) setDraft(initialDraft)
  }, [initialDraft, conversation?.my_role, conversation?.first_message_at])

  // Polling.
  useEffect(() => {
    const poll = () => {
      if (document.hidden) return
      polls.current += 1
      const params = lastId.current ? { after: lastId.current } : undefined
      fetchMessages(id, params)
        .then((data) => {
          take(data)
          const theyWrote = data.results.some((m) => !m.from_me)
          if (theyWrote) tellParent()
          if (theyWrote || polls.current % DETAIL_EVERY === 0) loadConversation()
        })
        .catch(() => {})
    }
    const timer = setInterval(poll, THREAD_POLL_MS)
    document.addEventListener('visibilitychange', poll)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', poll)
    }
  }, [id, take, loadConversation, tellParent])

  // Keep the newest message in view, unless the reader has scrolled up to read older ones.
  useEffect(() => {
    const log = logRef.current
    if (log && stickToBottom.current) log.scrollTop = log.scrollHeight
  }, [messages])

  const onScroll = () => {
    const log = logRef.current
    stickToBottom.current = log.scrollHeight - log.scrollTop - log.clientHeight < 80
  }

  const showEarlier = async () => {
    const first = messages.find((m) => m.id)
    if (!first) return
    stickToBottom.current = false
    try {
      const data = await fetchMessages(id, { before: first.id })
      setHasEarlier(data.has_earlier)
      setMessages((current) => merge(current, data.results))
    } catch {
      setNotice('Could not load earlier messages.')
    }
  }

  const deliver = async (text, key) => {
    setMessages((current) =>
      ordered([...current.filter((m) => m.key !== key), { key, body: text, from_me: true, status: 'sending' }])
    )
    stickToBottom.current = true
    try {
      const saved = await sendMessage(id, text)
      setMessages((current) => {
        const rest = current.filter((m) => m.key !== key)
        return rest.some((m) => m.id === saved.id) ? rest : ordered([...rest, saved])
      })
      lastId.current = Math.max(lastId.current || 0, saved.id)
      if (saved.safety_tip) setTip(saved.safety_tip)
      if (!conversation?.first_message_at) loadConversation()
      tellParent()
    } catch (err) {
      const status = err?.response?.status
      let reason = 'Not sent.'
      if (status === 429) reason = 'Not sent: you are sending messages too quickly. Wait a moment.'
      else if (status === 403) reason = `Not sent: ${errorText(err, 'you cannot write in this chat.')}`
      setMessages((current) => current.map((m) => (m.key === key ? { ...m, status: 'failed', reason } : m)))
      if (status === 403) loadConversation()
    }
  }

  const submit = (e) => {
    e?.preventDefault()
    const text = draft.trim()
    if (!text || !conversation?.can_send) return
    setDraft('')
    pendingCount += 1
    deliver(text, `pending-${pendingCount}`)
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  const report = async (reason) => {
    try {
      const data = await reportConversation(id, reason)
      setReporting(false)
      setNotice(data.detail)
    } catch (err) {
      throw new Error(errorText(err, 'Could not send your report. Try again.'))
    }
  }

  if (loadError) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-8">
        <p className="text-section-title text-ink">{loadError}</p>
        <Link to="/messages" className="mt-2 text-label text-primary hover:underline">
          Back to messages
        </Link>
      </div>
    )
  }
  if (!conversation) return <ThreadSkeleton />

  const name = conversation.other.full_name
  const lastOwn = [...messages].reverse().find((m) => m.from_me)
  const seenId = lastOwn?.id && seenUpTo && lastOwn.id <= seenUpTo ? lastOwn.id : null
  const waiting = conversation.waiting_for_client && conversation.my_role === 'freelancer'
  const disabled = !conversation.can_send

  let placeholder = `Message ${name}`
  if (conversation.read_only_reason) placeholder = 'This chat is read-only'
  else if (waiting) placeholder = `Waiting for ${name} to start the conversation`

  let previousDay = null

  return (
    <div className="flex flex-col h-full min-h-0">
      <header className="flex items-center gap-3 px-4 sm:px-5 py-4 border-b border-line">
        <Link
          to="/messages"
          aria-label="Back to messages"
          className="md:hidden -ml-1 w-10 h-10 rounded-full flex items-center justify-center text-ink-soft hover:bg-sand"
        >
          <ArrowLeft size={20} aria-hidden="true" />
        </Link>
        <Avatar name={name} />
        <div className="min-w-0 flex-1">
          <h2 className="text-[17px] leading-6 font-bold text-ink truncate">{name}</h2>
          <p className="text-caption text-muted truncate">
            <Link to={`/gigs/${conversation.gig.id}`} className="text-primary font-semibold hover:underline">
              {conversation.gig.title}
            </Link>
            {conversation.hired_at && <> · Hired {longDate(conversation.hired_at)}</>}
          </p>
        </div>
        <button
          type="button"
          aria-label="Report this chat"
          onClick={() => setReporting(true)}
          className="shrink-0 min-h-[40px] px-3 rounded-pill text-label text-ink-soft hover:bg-sand hover:text-ink inline-flex items-center gap-1.5"
        >
          <Flag size={16} aria-hidden="true" />
          <span className="hidden sm:inline">Report</span>
        </button>
      </header>

      <div
        ref={logRef}
        onScroll={onScroll}
        role="log"
        aria-live="polite"
        aria-label={`Messages with ${name}`}
        className="flex-1 min-h-0 overflow-y-auto px-4 sm:px-5 py-4 bg-bg"
      >
        {hasEarlier && (
          <div className="text-center mb-3">
            <button type="button" onClick={showEarlier} className="text-label text-primary hover:underline min-h-[40px]">
              Show earlier messages
            </button>
          </div>
        )}

        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center px-6 py-10">
            <p className="text-section-title text-ink">No messages yet</p>
            <p className="text-body text-muted mt-1 max-w-sm">
              {conversation.my_role === 'client'
                ? `Say hello and explain the next steps. ${name} can reply once you send the first message.`
                : `${name} will message you here.`}
            </p>
          </div>
        )}

        <ol className="space-y-2">
          {messages.map((message) => {
            const day = message.created_at ? dayOf(message.created_at) : 'Today'
            const divider = day !== previousDay
            previousDay = day
            const mine = message.from_me
            return (
              <Fragment key={message.id || message.key}>
                {divider && (
                  <li className="text-center py-2">
                    <span className="text-caption font-semibold text-muted">{day}</span>
                  </li>
                )}
                <li className={`flex flex-col ${mine ? 'items-end' : 'items-start'}`}>
                  <span className="sr-only">{mine ? 'You' : name}: </span>
                  <p
                    className={`max-w-[85%] sm:max-w-[70%] whitespace-pre-wrap break-words px-4 py-2.5 text-[15px] leading-[22px] rounded-tile ${
                      mine
                        ? 'bg-primary text-white rounded-br-[6px]'
                        : 'bg-surface text-ink shadow-ring-border rounded-bl-[6px]'
                    } ${message.status === 'sending' ? 'opacity-70' : ''}`}
                  >
                    {message.body}
                  </p>
                  <span className="text-[12px] leading-4 text-muted mt-1 px-1">
                    {message.status === 'sending' && 'Sending…'}
                    {message.status === 'failed' && (
                      <span className="text-coral-ink">
                        {message.reason}{' '}
                        <button
                          type="button"
                          onClick={() => deliver(message.body, message.key)}
                          className="font-semibold underline"
                        >
                          Retry
                        </button>
                      </span>
                    )}
                    {message.created_at && timeOf(message.created_at)}
                    {message.id && message.id === seenId && <> · Seen</>}
                  </span>
                </li>
              </Fragment>
            )
          })}
        </ol>
      </div>

      <div className="border-t border-line pt-3 bg-surface">
        {notice && (
          <div role="status" className="mx-4 sm:mx-5 mb-3 rounded-input bg-accent-light px-4 py-3 text-[14px] leading-5 text-accent font-semibold">
            {notice}
          </div>
        )}
        {conversation.read_only_reason && <Banner icon={Lock}>{conversation.read_only_reason}</Banner>}
        {!conversation.read_only_reason && waiting && (
          <Banner icon={Lock}>Waiting for {name} to start the conversation. You can reply once they write.</Banner>
        )}
        {tip && (
          <div className="mx-4 sm:mx-5 mb-3 flex items-start gap-2.5 rounded-input bg-sun-light px-4 py-3 text-[14px] leading-5 text-sun-deep">
            <ShieldCheck size={18} aria-hidden="true" className="mt-px shrink-0" />
            <p role="status" className="flex-1">
              {tip}
            </p>
            <button type="button" onClick={() => setTip('')} className="font-semibold underline shrink-0">
              OK
            </button>
          </div>
        )}

        <form onSubmit={submit} className="px-4 sm:px-5 pb-4 flex items-end gap-2">
          <div className="flex-1 min-w-0">
            <label htmlFor={inputId} className="sr-only">
              Message {name}
            </label>
            <textarea
              id={inputId}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              disabled={disabled}
              placeholder={placeholder}
              maxLength={MESSAGE_MAX_LENGTH}
              rows={draft.split('\n').length > 1 || draft.length > 80 ? 4 : 2}
              aria-describedby={draft.length >= COUNTER_FROM ? counterId : undefined}
              className="block w-full resize-none rounded-input border border-border bg-surface px-3.5 py-2.5 text-[15px] leading-[22px] text-ink placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-primary disabled:bg-sand disabled:cursor-not-allowed"
            />
            <div className="flex justify-between gap-3 mt-1 text-[12px] leading-4 text-muted">
              <span className="hidden sm:inline">{disabled ? '' : 'Enter to send, Shift+Enter for a new line'}</span>
              {draft.length >= COUNTER_FROM && (
                <span id={counterId} className={`ml-auto ${draft.length >= MESSAGE_MAX_LENGTH ? 'text-coral-ink font-semibold' : ''}`}>
                  {draft.length.toLocaleString('en-US')} / {MESSAGE_MAX_LENGTH.toLocaleString('en-US')}
                </span>
              )}
            </div>
          </div>
          <button
            type="submit"
            disabled={disabled || !draft.trim()}
            className="mb-5 shrink-0 w-12 h-12 rounded-button bg-primary text-white flex items-center justify-center hover:bg-primary-hover disabled:bg-disabled disabled:text-muted disabled:cursor-not-allowed"
          >
            <Send size={20} aria-hidden="true" />
            <span className="sr-only">Send</span>
          </button>
        </form>
      </div>

      <ConfirmDialog
        open={reporting}
        title="Report this chat"
        description="An administrator will read this whole chat to look into it. Every time an administrator opens a reported chat, it is recorded."
        reasonLabel="What is wrong?"
        reasonHint="For example: asking to be paid outside GigConnect, or abusive messages."
        confirmLabel="Report chat"
        onConfirm={report}
        onCancel={() => setReporting(false)}
      />
    </div>
  )
}
