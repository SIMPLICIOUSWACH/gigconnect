import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Eye } from 'lucide-react'
import { errorMessage, fetchChatReport, resolveChatReport, suspendUser } from '../api'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'
import { ErrorBox, Pill, SkeletonBlock, dangerButton, primaryButton } from '../components/ui'
import { formatDateTime } from '../format'

function Person({ person, role, onSuspend }) {
  const suspended = person.account_status === 'suspended'
  return (
    <div className="flex flex-wrap items-center gap-3 justify-between bg-surface rounded-tile shadow-hairline px-4 py-3">
      <div>
        <p className="text-caption text-muted">{role}</p>
        <Link to={`/admin/users/${person.id}`} className="font-semibold text-primary hover:underline">
          {person.full_name}
        </Link>
      </div>
      {suspended ? (
        <Pill tone="coral">Suspended</Pill>
      ) : (
        person.account_status === 'active' && (
          <button type="button" className={dangerButton} onClick={() => onSuspend(person)}>
            Suspend
            <span className="sr-only"> {person.full_name}</span>
          </button>
        )
      )}
    </div>
  )
}

/*
  One reported chat: the reports, then the whole conversation, read-only. Loading this page is what the server records
  as "Viewed reported chat", so it loads once per visit (React's development double render doesn't count twice).
*/
export default function ChatReportPage() {
  const { id } = useParams()
  const toast = useToast()
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [resolving, setResolving] = useState(false)
  const [suspending, setSuspending] = useState(null)
  const loadedFor = useRef(null)

  useEffect(() => {
    if (loadedFor.current === id) return
    loadedFor.current = id
    setReport(null)
    setError('')
    fetchChatReport(id)
      .then(setReport)
      .catch((err) => setError(errorMessage(err, 'Could not load this report.')))
  }, [id])

  const resolve = async (note) => {
    try {
      const updated = await resolveChatReport(id, note)
      setReport((current) => ({ ...current, ...updated }))
      setResolving(false)
      toast?.('Report resolved.')
    } catch (err) {
      throw new Error(errorMessage(err, 'Could not resolve this report.'))
    }
  }

  const suspend = async (reason) => {
    const person = suspending
    try {
      await suspendUser(person.id, reason)
      const mark = (p) => (p?.id === person.id ? { ...p, account_status: 'suspended' } : p)
      setReport((current) => ({ ...current, client: mark(current.client), freelancer: mark(current.freelancer) }))
      setSuspending(null)
      toast?.(`${person.full_name} is suspended.`)
    } catch (err) {
      throw new Error(errorMessage(err, 'Could not suspend this account.'))
    }
  }

  if (error) return <ErrorBox>{error}</ErrorBox>
  if (!report) {
    return (
      <div aria-label="Loading the report" className="space-y-4">
        <SkeletonBlock className="h-10 w-1/2" />
        <SkeletonBlock className="h-32" />
        <SkeletonBlock className="h-64" />
      </div>
    )
  }

  const clientId = report.client.id

  return (
    <div className="max-w-[860px]">
      <Link to="/admin/chat-reports" className="inline-block text-label text-primary hover:underline mb-3">
        All reported chats
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-2">
        <h1 className="text-page-title text-ink">Reported chat</h1>
        {report.resolved_at ? <Pill tone="mint">Resolved</Pill> : <Pill tone="sun">Open</Pill>}
      </div>
      <p className="text-body text-ink-soft mb-4">
        About{' '}
        <Link to={`/admin/gigs/${report.gig.id}`} className="text-primary font-semibold hover:underline">
          {report.gig.title}
        </Link>
      </p>

      <p className="flex items-start gap-2 rounded-input bg-sun-light text-sun-deep px-4 py-3 text-[14px] leading-5 mb-6">
        <Eye size={18} aria-hidden="true" className="mt-px shrink-0" />
        Opening this chat was recorded in the audit log under your name. Read only what you need to decide.
      </p>

      <div className="grid sm:grid-cols-2 gap-3 mb-6">
        <Person person={report.client} role="Client" onSuspend={setSuspending} />
        <Person person={report.freelancer} role="Freelancer" onSuspend={setSuspending} />
      </div>

      <section aria-labelledby="reports-heading" className="mb-6">
        <h2 id="reports-heading" className="text-section-title text-ink mb-3">
          {report.reports.length === 1 ? 'The report' : `Reports (${report.reports.length})`}
        </h2>
        <ul className="space-y-2">
          {report.reports.map((item) => (
            <li key={item.id} className="bg-surface rounded-tile shadow-hairline p-4">
              <p className="text-caption text-muted">
                {item.reporter.full_name} · {formatDateTime(item.created_at)}
                {item.resolved_at && ` · Resolved by ${item.resolved_by?.full_name || 'an admin'}`}
              </p>
              <p className="text-body text-ink mt-1 whitespace-pre-line break-words">{item.reason}</p>
              {item.resolution_note && <p className="text-caption text-muted mt-1">Note: {item.resolution_note}</p>}
            </li>
          ))}
        </ul>
        {!report.resolved_at && (
          <button type="button" className={`${primaryButton} mt-4`} onClick={() => setResolving(true)}>
            Resolve report
          </button>
        )}
      </section>

      <section aria-labelledby="chat-heading">
        <h2 id="chat-heading" className="text-section-title text-ink mb-3">
          The chat ({report.messages.length} {report.messages.length === 1 ? 'message' : 'messages'})
        </h2>
        {report.messages.length === 0 ? (
          <p className="text-body text-muted">Nobody has written in this chat yet.</p>
        ) : (
          <ol className="space-y-2 bg-bg rounded-card p-4 border border-line">
            {report.messages.map((message) => {
              const fromClient = message.sender.id === clientId
              return (
                <li key={message.id} className={`flex flex-col ${fromClient ? 'items-start' : 'items-end'}`}>
                  <span className="text-[12px] leading-4 text-muted mb-1 px-1">
                    {message.sender.full_name} ({fromClient ? 'client' : 'freelancer'}) · {formatDateTime(message.created_at)}
                  </span>
                  <p
                    className={`max-w-[85%] whitespace-pre-wrap break-words px-4 py-2.5 text-[15px] leading-[22px] rounded-tile ${
                      fromClient ? 'bg-surface text-ink shadow-ring-border' : 'bg-primary-light text-ink'
                    }`}
                  >
                    {message.body}
                  </p>
                </li>
              )
            })}
          </ol>
        )}
      </section>

      <ConfirmDialog
        open={resolving}
        title="Resolve this report?"
        description="The report moves to Resolved. Suspend an account first if the chat calls for it."
        confirmLabel="Resolve report"
        reasonLabel="Note"
        reasonHint="For the audit log. The people in the chat don't see it."
        reasonRequired={false}
        onConfirm={resolve}
        onCancel={() => setResolving(false)}
      />
      <ConfirmDialog
        open={Boolean(suspending)}
        title={suspending ? `Suspend ${suspending.full_name}?` : ''}
        description="They are logged out everywhere and can't log in until reinstated. Their open gigs are hidden and their chats become read-only. You can undo this."
        confirmLabel="Suspend account"
        onConfirm={suspend}
        onCancel={() => setSuspending(null)}
      />
    </div>
  )
}
