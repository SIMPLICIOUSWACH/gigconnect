import { Link } from 'react-router-dom'
import { fetchApplications, removeApplication, restoreApplication } from '../api'
import ConfirmDialog from '../components/ConfirmDialog'
import {
  Cell,
  DataTable,
  EmptyRow,
  ErrorBox,
  Field,
  FilterBar,
  PageHeader,
  Pager,
  RemovedPill,
  SkeletonRows,
  dangerButton,
  fieldClass,
  quietButton,
} from '../components/ui'
import { APPLICATION_STATUS, formatDate } from '../format'
import { useAdminData, withRow } from '../useAdminData'
import { useModeration } from '../useModeration'
import { useUrlFilters } from '../useUrlFilters'

const COLUMNS = ['Freelancer', 'Gig', 'Status', 'Cover letter', 'Applied', 'Action']

function describe(row) {
  return `${row.freelancer.full_name}'s application for "${row.gig.title}"`
}

// The gig, freelancer or single application the list is narrowed to, named from the rows themselves.
function ActiveScope({ filters, rows, onClear }) {
  const first = rows?.[0]
  const scopes = [
    filters.id && { key: 'id', text: 'One application' },
    filters.gig && { key: 'gig', text: `Gig: ${first?.gig.title || 'no applications'}` },
    filters.freelancer && { key: 'freelancer', text: `Freelancer: ${first?.freelancer.full_name || 'no applications'}` },
  ].filter(Boolean)
  if (scopes.length === 0) return null
  return (
    <ul className="flex flex-wrap gap-2 mb-3" aria-label="Showing only">
      {scopes.map((scope) => (
        <li key={scope.key}>
          <button
            type="button"
            onClick={() => onClear(scope.key)}
            className="inline-flex items-center gap-2 text-label bg-ink text-white px-3 py-1.5 rounded-pill"
          >
            {scope.text}
            <span aria-hidden="true">×</span>
            <span className="sr-only">, show all instead</span>
          </button>
        </li>
      ))}
    </ul>
  )
}

export default function ApplicationsPage() {
  const { filters, page, setFilter, setPage, key } = useUrlFilters(['id', 'gig', 'freelancer', 'status', 'moderation'])
  const { data, setData, error, loading, reload } = useAdminData(() => fetchApplications({ ...filters, page }), key)
  const moderation = useModeration({
    remove: removeApplication,
    restore: restoreApplication,
    onUpdated: (row) => setData((current) => withRow(current, row)),
    describe,
  })
  const { pending } = moderation

  return (
    <>
      <PageHeader title="Applications">
        Every application. A removed application is hidden from the client; the freelancer still sees it, marked
        removed.
      </PageHeader>

      <FilterBar>
        <Field label="Status">
          <select value={filters.status} onChange={(e) => setFilter('status', e.target.value)} className={fieldClass}>
            <option value="">Any status</option>
            {Object.entries(APPLICATION_STATUS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Moderation">
          <select value={filters.moderation} onChange={(e) => setFilter('moderation', e.target.value)} className={fieldClass}>
            <option value="">Visible and removed</option>
            <option value="visible">Visible</option>
            <option value="removed">Removed</option>
          </select>
        </Field>
        <p className="text-caption text-muted sm:col-span-2 self-center">
          To see one gig&apos;s or one freelancer&apos;s applications, open the gig or the user and follow the link there.
        </p>
      </FilterBar>

      <ActiveScope filters={filters} rows={data?.results} onClear={(name) => setFilter(name, '')} />
      {error && <ErrorBox onRetry={reload}>{error}</ErrorBox>}
      {data && <p className="text-caption text-muted mb-2">{data.count} {data.count === 1 ? 'application' : 'applications'}</p>}

      <DataTable caption="Applications" columns={COLUMNS}>
        {loading && !data ? (
          <SkeletonRows columns={COLUMNS.length} />
        ) : data?.results.length === 0 ? (
          <EmptyRow columns={COLUMNS.length}>No applications match these filters.</EmptyRow>
        ) : (
          data?.results.map((row) => {
            const removed = row.moderation_status === 'removed'
            return (
              <tr key={row.id} className="hover:bg-sand/60">
                <Cell>
                  <Link to={`/admin/users/${row.freelancer.id}`} className="font-semibold text-primary hover:underline">
                    {row.freelancer.full_name}
                  </Link>
                </Cell>
                <Cell>
                  <Link to={`/admin/gigs/${row.gig.id}`} className="hover:underline">
                    {row.gig.title}
                  </Link>
                  <span className="block text-caption text-muted">Client: {row.client.full_name}</span>
                </Cell>
                <Cell>
                  <span className="flex flex-wrap gap-1.5 items-center">
                    {APPLICATION_STATUS[row.status]}
                    {removed && <RemovedPill />}
                  </span>
                  {removed && row.removed_reason && <span className="block text-caption text-coral-ink mt-1">{row.removed_reason}</span>}
                </Cell>
                <Cell className="max-w-[320px]">
                  <details>
                    <summary className="cursor-pointer text-ink-soft line-clamp-2">{row.cover_letter}</summary>
                    <p className="mt-2 whitespace-pre-line break-words">{row.cover_letter}</p>
                    {row.portfolio_link && (
                      <p className="mt-2 text-caption break-all">Portfolio link: {row.portfolio_link}</p>
                    )}
                  </details>
                </Cell>
                <Cell className="whitespace-nowrap">{formatDate(row.created_at)}</Cell>
                <Cell>
                  {removed ? (
                    <button type="button" className={quietButton} onClick={() => moderation.askRestore(row)}>
                      Restore
                      <span className="sr-only"> {describe(row)}</span>
                    </button>
                  ) : (
                    <button type="button" className={dangerButton} onClick={() => moderation.askRemove(row)}>
                      Remove
                      <span className="sr-only"> {describe(row)}</span>
                    </button>
                  )}
                </Cell>
              </tr>
            )
          })
        )}
      </DataTable>
      <Pager data={data} page={page} onPage={setPage} />

      <ConfirmDialog
        open={pending?.kind === 'remove'}
        title="Remove this application?"
        description={pending && `${describe(pending.row)} will be hidden from the client. The freelancer sees it marked removed, with your reason.`}
        confirmLabel="Remove application"
        onConfirm={moderation.confirm}
        onCancel={moderation.cancel}
      />
      <ConfirmDialog
        open={pending?.kind === 'restore'}
        title="Restore this application?"
        description={pending && `${describe(pending.row)} will be shown to the client again.`}
        confirmLabel="Restore application"
        reasonRequired={false}
        onConfirm={moderation.confirm}
        onCancel={moderation.cancel}
      />
    </>
  )
}
