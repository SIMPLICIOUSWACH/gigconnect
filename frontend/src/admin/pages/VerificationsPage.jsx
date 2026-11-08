import { useEffect, useId, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { decideVerification, errorMessage, fetchVerificationDocument, fetchVerifications } from '../api'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'
import ZoomableImage from '../components/ZoomableImage'
import { EmptyState, ErrorBox, PageHeader, SkeletonBlock, dangerButton, primaryButton } from '../components/ui'
import { formatDateTime } from '../format'
import { useAdmin, useAdminData } from '../useAdminData'

const QUEUE_SIZE = 50

export const CHECKLIST = [
  { key: 'same_person', label: 'Same person in both photos' },
  { key: 'id_matches', label: 'ID visible in the selfie and matches the uploaded ID' },
  { key: 'challenge_done', label: 'Challenge gesture performed correctly' },
]

// The quick rejection reasons, and what the freelancer is asked to redo by default for each.
export const REJECTION_REASONS = [
  { code: 'face_mismatch', label: "Face doesn't match", redo: 'both' },
  { code: 'challenge_not_performed', label: 'Challenge not performed', redo: 'selfie' },
  { code: 'id_not_visible', label: 'ID not visible in the selfie', redo: 'selfie' },
  { code: 'photo_unclear', label: 'Photo unclear', redo: 'selfie' },
  { code: 'other', label: 'Other', redo: 'both' },
]

const REDO_OPTIONS = [
  { value: 'id', label: 'Only the ID' },
  { value: 'selfie', label: 'Only the selfie' },
  { value: 'both', label: 'Both the ID and the selfie' },
]

// A file only admins can read (the ID or the selfie), fetched with the admin's token and shown from a local URL.
function useProtectedFile(profileId, kind, wanted) {
  const [file, setFile] = useState({ url: '', type: '', error: '' })

  useEffect(() => {
    if (!wanted) return undefined
    let url = ''
    let alive = true
    setFile({ url: '', type: '', error: '' })
    fetchVerificationDocument(profileId, kind)
      .then((blob) => {
        if (!alive) return
        url = URL.createObjectURL(blob)
        setFile({ url, type: blob.type, error: '' })
      })
      .catch((err) => alive && setFile({ url: '', type: '', error: errorMessage(err, 'Could not load the file.') }))
    return () => {
      alive = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [profileId, kind, wanted])

  return file
}

function IdPanel({ item }) {
  const file = useProtectedFile(item.id, 'id', item.has_document)
  const name = item.user.full_name
  let body
  if (!item.has_document) body = <p className="text-body text-muted">No ID document was uploaded.</p>
  else if (file.error) body = <p className="text-body text-coral-ink">{file.error}</p>
  else if (!file.url) body = <SkeletonBlock className="h-72" />
  else if (file.type.startsWith('image/')) body = <ZoomableImage src={file.url} alt={`ID document sent by ${name}`} />
  else if (file.type === 'application/pdf') {
    body = (
      <div className="space-y-2">
        <iframe src={file.url} title={`ID document sent by ${name}`} className="w-full h-[420px] rounded-input bg-sand" />
        <a href={file.url} target="_blank" rel="noreferrer" className="text-caption text-primary font-semibold hover:underline">
          Open the PDF in a new tab to zoom
        </a>
      </div>
    )
  } else {
    // Only a real PDF goes in a frame. Anything else, from before uploads were checked, is a download: never run it here.
    body = (
      <p className="text-body text-ink-soft">
        This file type can&apos;t be shown here.{' '}
        <a href={file.url} download="id-document" className="text-primary font-semibold hover:underline">
          Download the document
        </a>
      </p>
    )
  }
  return (
    <figure className="space-y-2 min-w-0">
      <figcaption className="text-label text-ink">ID document</figcaption>
      {body}
    </figure>
  )
}

function SelfiePanel({ item }) {
  const file = useProtectedFile(item.id, 'selfie', item.has_selfie)
  let body
  if (!item.has_selfie) body = <p className="text-body text-muted">No selfie yet.</p>
  else if (file.error) body = <p className="text-body text-coral-ink">{file.error}</p>
  else if (!file.url) body = <SkeletonBlock className="h-72" />
  else body = <ZoomableImage src={file.url} alt={`Selfie sent by ${item.user.full_name}`} />
  return (
    <figure className="space-y-2 min-w-0">
      <figcaption className="text-label text-ink">Selfie</figcaption>
      {item.selfie_challenge && (
        <p className="rounded-input bg-sun-light text-sun-ink px-3 py-2 text-body">
          <span className="text-label block">Challenge they were given</span>
          {item.selfie_challenge}
        </p>
      )}
      {body}
    </figure>
  )
}

function SimilarityHint({ item }) {
  if (item.face_match_score === null || item.face_match_score === undefined) {
    return (
      <p className="text-caption text-muted">
        System similarity: {item.face_match_model || 'not available'}. Advisory only.
      </p>
    )
  }
  return (
    <p className="text-caption text-ink-soft">
      <span className="font-semibold">System similarity: {item.face_match_score.toFixed(2)}, advisory.</span> A hint
      from {item.face_match_model}, never a decision. Higher means the faces look more alike.
    </p>
  )
}

function Decision({ item, onApproved, onReject }) {
  const [ticked, setTicked] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const groupId = useId()
  const allTicked = CHECKLIST.every(({ key }) => ticked[key])

  const approve = async () => {
    setBusy(true)
    setError('')
    try {
      await decideVerification(item.id, { verification_status: 'verified', checklist: ticked })
      onApproved()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <fieldset aria-describedby={`${groupId}-hint`} className="space-y-2">
        <legend className="text-label text-ink">Before approving, check:</legend>
        <p id={`${groupId}-hint`} className="text-caption text-muted">
          Approve stays off until all three are ticked.
        </p>
        {CHECKLIST.map(({ key, label }) => (
          <label key={key} className="flex items-start gap-3 text-body text-ink">
            <input
              type="checkbox"
              checked={Boolean(ticked[key])}
              onChange={(e) => setTicked((current) => ({ ...current, [key]: e.target.checked }))}
              className="mt-1 w-5 h-5 accent-primary shrink-0"
            />
            {label}
          </label>
        ))}
      </fieldset>
      {error && <ErrorBox>{error}</ErrorBox>}
      <div className="flex flex-wrap gap-2">
        <button type="button" className={primaryButton} disabled={!allTicked || busy || !item.has_selfie} onClick={approve}>
          {busy ? 'Approving…' : 'Approve'}
        </button>
        <button type="button" className={dangerButton} disabled={busy} onClick={onReject}>
          Reject
        </button>
      </div>
    </div>
  )
}

function RejectDialog({ item, open, onCancel, onRejected }) {
  const [code, setCode] = useState('')
  const [redo, setRedo] = useState('')
  const nameId = useId()

  useEffect(() => {
    if (open) {
      setCode('')
      setRedo('')
    }
  }, [open])

  const choose = (reason) => {
    setCode(reason.code)
    setRedo(reason.redo)
  }

  const confirm = async (details) => {
    try {
      await decideVerification(item.id, { verification_status: 'rejected', reason_code: code, redo, reason: details })
    } catch (err) {
      throw new Error(errorMessage(err))
    }
    onRejected()
  }

  return (
    <ConfirmDialog
      open={open}
      title={`Reject ${item?.user.full_name}'s ID check?`}
      description="They are told the reason and asked to redo only the part you choose. The rest is kept."
      confirmLabel="Reject"
      reasonLabel={code === 'other' ? 'Reason' : 'More detail'}
      reasonHint={code === 'other' ? 'They see this.' : 'Added after the reason they see.'}
      reasonRequired={code === 'other'}
      validate={() => (code ? '' : 'Choose a reason.')}
      onConfirm={confirm}
      onCancel={onCancel}
    >
      <fieldset className="space-y-2 mb-4">
        <legend className="text-label text-ink">Reason</legend>
        {REJECTION_REASONS.map((reason) => (
          <label key={reason.code} className="flex items-center gap-3 text-body text-ink">
            <input
              type="radio"
              name={`${nameId}-reason`}
              checked={code === reason.code}
              onChange={() => choose(reason)}
              className="w-4 h-4 accent-primary"
            />
            {reason.label}
          </label>
        ))}
      </fieldset>
      <label className="block text-label text-ink mb-4">
        What they need to send again
        <select
          value={redo}
          onChange={(e) => setRedo(e.target.value)}
          className="mt-1 w-full min-h-[44px] rounded-input border border-border bg-surface px-3 text-body"
        >
          <option value="" disabled>
            Choose a reason first
          </option>
          {REDO_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    </ConfirmDialog>
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

  return (
    <>
      <PageHeader title="Verifications">
        ID checks waiting for a decision, oldest first. Compare the ID with the selfie, tick the checks, then approve
        or reject. The freelancer is told the outcome.
      </PageHeader>

      {error && <ErrorBox onRetry={reload}>{error}</ErrorBox>}

      {loading && !data ? (
        <div aria-label="Loading verifications" className="grid gap-4 lg:grid-cols-[260px_1fr]">
          <SkeletonBlock className="h-64" />
          <SkeletonBlock className="h-96" />
        </div>
      ) : queue.length === 0 ? (
        !error && <EmptyState title="All caught up">No ID checks are waiting for a decision.</EmptyState>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[260px_1fr] items-start">
          <section aria-label="Queue" className="bg-surface rounded-card shadow-hairline p-2 min-w-0">
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

          <section aria-labelledby="current-heading" className="bg-surface rounded-card shadow-hairline p-6 min-w-0 space-y-5">
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

            {selected.same_id_elsewhere?.length > 0 && (
              <div role="note" className="rounded-input bg-coral-light text-coral-ink px-4 py-3 text-body">
                The same ID number is on another account:{' '}
                {selected.same_id_elsewhere.map((other, index) => (
                  <span key={other.id}>
                    {index > 0 && ', '}
                    <Link to={`/admin/users/${other.id}`} className="font-semibold underline">
                      {other.full_name}
                    </Link>
                  </span>
                ))}
              </div>
            )}

            <div key={selected.id} className="grid gap-4 sm:grid-cols-2">
              <IdPanel item={selected} />
              <SelfiePanel item={selected} />
            </div>

            <SimilarityHint item={selected} />

            <Decision
              key={`decision-${selected.id}`}
              item={selected}
              onApproved={() => done(selected, `${selected.user.full_name}'s ID is approved.`)}
              onReject={() => setRejecting(true)}
            />
          </section>
        </div>
      )}

      <RejectDialog
        item={selected}
        open={rejecting}
        onCancel={() => setRejecting(false)}
        onRejected={() => {
          setRejecting(false)
          done(selected, `${selected.user.full_name}'s ID check was rejected.`)
        }}
      />
    </>
  )
}
