import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { errorMessage, fetchUser, reinstateUser, suspendUser } from '../api'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'
import { EmptyState, ErrorBox, Pill, RemovedPill, SkeletonBlock, dangerButton, quietButton } from '../components/ui'
import {
  ACCOUNT_STATUS,
  ACTION_LABELS,
  APPLICATION_STATUS,
  GIG_STATUS,
  ROLE_LABELS,
  VERIFICATION,
  formatDate,
  formatDateTime,
} from '../format'
import { useAdminData } from '../useAdminData'

function Section({ title, children }) {
  return (
    <section className="bg-surface rounded-card shadow-hairline p-6">
      <h2 className="text-section-title text-ink mb-3">{title}</h2>
      {children}
    </section>
  )
}

function Detail({ label, children }) {
  return (
    <div>
      <dt className="text-caption text-muted">{label}</dt>
      <dd className="text-body text-ink break-words">{children || <span className="text-muted">Not given</span>}</dd>
    </div>
  )
}

export default function UserDetailPage() {
  const { id } = useParams()
  const { data: user, setData, error, loading, reload } = useAdminData(() => fetchUser(id), id)
  const [dialog, setDialog] = useState(null)
  const toast = useToast()

  if (error) return <ErrorBox onRetry={reload}>{error}</ErrorBox>
  if (loading && !user) {
    return (
      <div aria-label="Loading user" className="space-y-4">
        <SkeletonBlock className="h-40" />
        <SkeletonBlock className="h-56" />
      </div>
    )
  }

  const status = ACCOUNT_STATUS[user.status]
  const verification = VERIFICATION[user.verification_status]
  const canSuspend = user.status === 'active' && user.role !== 'admin'

  const act = async (reason) => {
    const suspend = dialog === 'suspend'
    try {
      const row = await (suspend ? suspendUser(user.id, reason) : reinstateUser(user.id, reason))
      setData({ ...user, ...row, suspended_reason: suspend ? reason : '' })
      setDialog(null)
      toast(suspend ? `${user.full_name} is suspended.` : `${user.full_name} is active again.`)
      reload()
    } catch (err) {
      throw new Error(errorMessage(err))
    }
  }

  return (
    <div className="space-y-4">
      <Link to="/admin/users" className="text-body text-primary font-semibold hover:underline">
        Back to users
      </Link>

      <section className="bg-surface rounded-card shadow-hairline p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-page-title text-ink break-words">{user.full_name || 'No name given'}</h1>
            <p className="text-body text-ink-soft break-all">{user.email}</p>
            <div className="flex flex-wrap gap-2 mt-3">
              <Pill tone="ocean">{ROLE_LABELS[user.role]}</Pill>
              <Pill tone={status.tone}>{status.label}</Pill>
              {verification && <Pill tone={verification.tone}>{verification.label}</Pill>}
              {user.is_synthetic && <Pill>Synthetic</Pill>}
            </div>
          </div>
          {canSuspend && (
            <button type="button" className={dangerButton} onClick={() => setDialog('suspend')}>
              Suspend account
            </button>
          )}
          {user.status === 'suspended' && (
            <button type="button" className={quietButton} onClick={() => setDialog('reinstate')}>
              Reinstate account
            </button>
          )}
        </div>

        {user.status === 'suspended' && (
          <p className="mt-4 rounded-input bg-coral-light text-coral-ink px-4 py-3 text-body">
            Suspended {formatDateTime(user.suspended_at)}. Reason: {user.suspended_reason}
          </p>
        )}

        <dl className="grid gap-4 sm:grid-cols-3 mt-6">
          <Detail label="Joined">{formatDate(user.created_at)}</Detail>
          <Detail label="Phone">{user.phone}</Detail>
          <Detail label="Email verified">{user.is_email_verified ? 'Yes' : 'No'}</Detail>
          {user.profile && user.role === 'freelancer' && (
            <>
              <Detail label="Headline">{user.profile.headline}</Detail>
              <Detail label="County">{user.profile.county}</Detail>
              <Detail label="Skills">{user.profile.skills.join(', ')}</Detail>
            </>
          )}
          {user.profile && user.role === 'client' && (
            <>
              <Detail label="Company">{user.profile.company_name}</Detail>
              <Detail label="Industry">{user.profile.industry}</Detail>
            </>
          )}
        </dl>
      </section>

      {user.role !== 'freelancer' && (
        <Section title={`Gigs posted (${user.gigs.length})`}>
          {user.gigs.length === 0 ? (
            <EmptyState title="No gigs">This user hasn't posted a gig.</EmptyState>
          ) : (
            <ul className="divide-y divide-line">
              {user.gigs.map((gig) => (
                <li key={gig.id} className="py-3 flex flex-wrap items-center gap-3">
                  <Link to={`/admin/gigs/${gig.id}`} className="text-body font-semibold text-primary hover:underline">
                    {gig.title}
                  </Link>
                  <span className="text-caption text-muted">{GIG_STATUS[gig.status]}</span>
                  {gig.moderation_status === 'removed' && <RemovedPill />}
                  <span className="text-caption text-muted ml-auto">{formatDate(gig.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>
      )}

      {user.role === 'freelancer' && (
        <Section title={`Applications (${user.applications.length})`}>
          {user.applications.length === 0 ? (
            <EmptyState title="No applications">This freelancer hasn't applied to a gig.</EmptyState>
          ) : (
            <ul className="divide-y divide-line">
              {user.applications.map((application) => (
                <li key={application.id} className="py-3 flex flex-wrap items-center gap-3">
                  <Link
                    to={`/admin/applications?id=${application.id}`}
                    className="text-body font-semibold text-primary hover:underline"
                  >
                    {application.gig.title}
                  </Link>
                  <span className="text-caption text-muted">{APPLICATION_STATUS[application.status]}</span>
                  {application.moderation_status === 'removed' && <RemovedPill />}
                  <span className="text-caption text-muted ml-auto">{formatDate(application.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>
      )}

      <Section title="Admin history">
        {user.history.length === 0 ? (
          <p className="text-body text-muted">No admin has acted on this account, its gigs or its applications.</p>
        ) : (
          <ul className="divide-y divide-line">
            {user.history.map((row) => (
              <li key={row.id} className="py-3">
                <p className="text-body text-ink">
                  <span className="font-semibold">{ACTION_LABELS[row.action]}</span>
                  {row.target_type !== 'user' && row.target_label && <> · {row.target_label}</>}
                </p>
                <p className="text-caption text-muted">
                  {formatDateTime(row.created_at)} by {row.admin?.full_name || 'a removed admin'}
                </p>
                {row.reason && <p className="text-body text-ink-soft mt-1">{row.reason}</p>}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <ConfirmDialog
        open={dialog === 'suspend'}
        title={`Suspend ${user.full_name}?`}
        description="They are logged out everywhere and can't log in until reinstated. Their open gigs are hidden. You can undo this."
        confirmLabel="Suspend account"
        onConfirm={act}
        onCancel={() => setDialog(null)}
      />
      <ConfirmDialog
        open={dialog === 'reinstate'}
        title={`Reinstate ${user.full_name}?`}
        description="They can log in again and their open gigs are shown again."
        confirmLabel="Reinstate account"
        reasonRequired={false}
        onConfirm={act}
        onCancel={() => setDialog(null)}
      />
    </div>
  )
}
