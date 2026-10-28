import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { decideVerification, errorMessage, fetchVerificationDocument, fetchVerifications } from '../api'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'
import { EmptyState, ErrorBox, PageHeader, SkeletonBlock, dangerButton, primaryButton } from '../components/ui'
import { formatDateTime } from '../format'
import { useAdmin, useAdminData } from '../useAdminData'

const QUEUE_SIZE = 50

// The ID document, fetched with the admin's token and shown from a local object URL.
function DocumentViewer({ profileId, name }) {
  const [file, setFile] = useState({ url: '', type: '', error: '' })

  useEffect(() => {
    let url = ''
    let alive = true
    setFile({ url: '', type: '', error: '' })
    fetchVerificationDocument(profileId)
      .then((blob) => {
        if (!alive) return
        url = URL.createObjectURL(blob)
        setFile({ url, type: blob.type, error: '' })
      })
      .catch((err) => alive && setFile({ url: '', type: '', error: errorMessage(err, 'Could not load the document.') }))
    return () => {
      alive = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [profileId])

  if (file.error) return <p className="text-body text-coral-ink">{file.error}</p>
  if (!file.url) return <SkeletonBlock className="h-80" />
  if (file.type.startsWith('image/')) {
    return <img src={file.url} alt={`ID document sent by ${name}`} className="w-full max-h-[480px] object-contain rounded-input bg-sand" />
  }
  return (
    <div className="space-y-2">
      <iframe src={file.url} title={`ID document sent by ${name}`} className="w-full h-[480px] rounded-input bg-sand" />
      <a href={file.url} target="_blank" rel="noreferrer" className="text-body text-primary font-semibold hover:underline">
        Open the document in a new tab
      </a>
    </div>
  )
}

export default function VerificationsPage() {
  const [params, setParams] = useSearchParams()
  const { data, setData, error, loading, reload } = useAdminData(
    () => fetchVerifications({ page_size: QUEUE_SIZE }),
    'queue',
  )
  const { refreshPending } = useAdmin()
  const toast = useToast()
  const [rejecting, setRejecting] = useState(false)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState('')

  const queue = data?.results || []
  const selected = queue.find((item) => item.id === params.get('id')) || queue[0]

  const select = (id) => setParams(id ? { id } : {}, { replace: true })

  // After a decision the item leaves the queue and the next one opens, without leaving the page.
  const done = (item, message) => {
    const index = queue.findIndex((row) => row.id === item.id)
    const rest = queue.filter((row) => row.id !== item.id)
    setData({ ...data, count: data.count - 1, results: rest })
    select(rest[Math.min(index, rest.length - 1)]?.id)
    refreshPending()
    toast(message)
  }

  const approve = async () => {
    setBusy(true)
    setActionError('')
    try {
      await decideVerification(selected.id, 'verified')
      done(selected, `${selected.user.full_name}'s ID is approved.`)
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const reject = async (reason) => {
    try {
      await decideVerification(selected.id, 'rejected', reason)
    } catch (err) {
      throw new Error(errorMessage(err))
    }
    setRejecting(false)
    done(selected, `${selected.user.full_name}'s ID was rejected.`)
  }

  return (
    <>
      <PageHeader title="Verifications">
        ID documents waiting for a decision, oldest first. The freelancer is told the outcome, and the reason if you
        reject it.
      </PageHeader>

      {error && <ErrorBox onRetry={reload}>{error}</ErrorBox>}

      {loading && !data ? (
        <div aria-label="Loading verifications" className="grid gap-4 lg:grid-cols-[280px_1fr]">
          <SkeletonBlock className="h-64" />
          <SkeletonBlock className="h-96" />
        </div>
      ) : queue.length === 0 ? (
        !error && <EmptyState title="All caught up">No ID documents are waiting for a decision.</EmptyState>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[280px_1fr] items-start">
          <section aria-label="Queue" className="bg-surface rounded-card shadow-hairline p-2">
            <p className="text-caption text-muted px-3 pt-2 pb-1">
              {data.count} waiting{data.count > queue.length ? `, showing the oldest ${queue.length}` : ''}
            </p>
            <ul>
              {queue.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    aria-current={item.id === selected.id ? 'true' : undefined}
                    onClick={() => select(item.id)}
                    className={`w-full text-left px-3 py-2.5 rounded-button ${
                      item.id === selected.id ? 'bg-ink text-white' : 'hover:bg-sand text-ink'
                    }`}
                  >
                    <span className="block text-body font-semibold truncate">{item.user.full_name}</span>
                    <span className={`block text-caption ${item.id === selected.id ? 'text-white/80' : 'text-muted'}`}>
                      {item.verification_submitted_at ? `Sent ${formatDateTime(item.verification_submitted_at)}` : 'Date not recorded'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="current-heading" className="bg-surface rounded-card shadow-hairline p-6 min-w-0">
            <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
              <div className="min-w-0">
                <h2 id="current-heading" className="text-section-title text-ink">
                  {selected.user.full_name}
                </h2>
                <p className="text-body text-ink-soft break-all">{selected.email}</p>
                <p className="text-body text-ink mt-2">
                  ID number: <span className="font-semibold">{selected.id_number || 'Not given'}</span>
                </p>
                <Link to={`/admin/users/${selected.user.id}`} className="text-caption text-primary font-semibold hover:underline">
                  Open their account
                </Link>
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" className={primaryButton} disabled={busy} onClick={approve}>
                  {busy ? 'Approving…' : 'Approve'}
                </button>
                <button type="button" className={dangerButton} disabled={busy} onClick={() => setRejecting(true)}>
                  Reject
                </button>
              </div>
            </div>
            {actionError && <ErrorBox>{actionError}</ErrorBox>}
            {selected.has_document ? (
              <DocumentViewer profileId={selected.id} name={selected.user.full_name} />
            ) : (
              <p className="text-body text-muted">No document was uploaded with this request.</p>
            )}
          </section>
        </div>
      )}

      <ConfirmDialog
        open={rejecting}
        title={`Reject ${selected?.user.full_name}'s ID?`}
        description="They can send a new document from their settings."
        confirmLabel="Reject ID"
        reasonHint="Say what was wrong, so they can fix it. They see this."
        onConfirm={reject}
        onCancel={() => setRejecting(false)}
      />
    </>
  )
}
