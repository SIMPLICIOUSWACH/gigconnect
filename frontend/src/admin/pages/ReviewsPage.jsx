import { Link } from 'react-router-dom'
import { fetchReviews, removeReview, restoreReview } from '../api'
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
import { formatDate } from '../format'
import { useAdminData, withRow } from '../useAdminData'
import { useModeration } from '../useModeration'
import { useUrlFilters } from '../useUrlFilters'

const COLUMNS = ['Rating', 'Review', 'Freelancer', 'Client and gig', 'Written', 'Action']

function describe(row) {
  return `${row.client.full_name}'s review of ${row.freelancer.full_name}`
}

function Stars({ rating }) {
  return (
    <span className="whitespace-nowrap font-semibold text-ink">
      <span aria-hidden="true" className="text-sun">
        ★
      </span>{' '}
      {rating}
      <span className="sr-only"> out of 5</span>
    </span>
  )
}

export default function ReviewsPage() {
  const { filters, page, setFilter, setPage, clear, key } = useUrlFilters(['id', 'freelancer', 'client', 'rating', 'moderation'])
  const { data, setData, error, loading, reload } = useAdminData(() => fetchReviews({ ...filters, page }), key)
  const moderation = useModeration({
    remove: removeReview,
    restore: restoreReview,
    onUpdated: (row) => setData((current) => withRow(current, row)),
    describe,
  })
  const { pending } = moderation
  const narrowed = filters.id || filters.freelancer || filters.client

  return (
    <>
      <PageHeader title="Reviews">
        Every rating a client gave a freelancer. A removed review isn&apos;t shown and doesn&apos;t count towards the
        freelancer&apos;s rating.
      </PageHeader>

      <FilterBar>
        <Field label="Rating">
          <select value={filters.rating} onChange={(e) => setFilter('rating', e.target.value)} className={fieldClass}>
            <option value="">Any rating</option>
            {[5, 4, 3, 2, 1].map((value) => (
              <option key={value} value={value}>
                {value} {value === 1 ? 'star' : 'stars'}
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
      </FilterBar>

      {narrowed && (
        <p className="mb-3">
          <button
            type="button"
            onClick={clear}
            className="inline-flex items-center gap-2 text-label bg-ink text-white px-3 py-1.5 rounded-pill"
          >
            Showing some reviews only
            <span aria-hidden="true">×</span>
            <span className="sr-only">, show all instead</span>
          </button>
        </p>
      )}
      {error && <ErrorBox onRetry={reload}>{error}</ErrorBox>}
      {data && <p className="text-caption text-muted mb-2">{data.count} {data.count === 1 ? 'review' : 'reviews'}</p>}

      <DataTable caption="Reviews" columns={COLUMNS}>
        {loading && !data ? (
          <SkeletonRows columns={COLUMNS.length} />
        ) : data?.results.length === 0 ? (
          <EmptyRow columns={COLUMNS.length}>No reviews match these filters.</EmptyRow>
        ) : (
          data?.results.map((row) => {
            const removed = row.moderation_status === 'removed'
            return (
              <tr key={row.id} className="hover:bg-sand/60">
                <Cell>
                  <Stars rating={row.rating} />
                  {removed && (
                    <span className="block mt-1">
                      <RemovedPill />
                    </span>
                  )}
                </Cell>
                <Cell className="max-w-[340px]">
                  {row.text ? (
                    <p className="whitespace-pre-line break-words">{row.text}</p>
                  ) : (
                    <span className="text-muted">No text</span>
                  )}
                  {row.freelancer_reply && (
                    <p className="mt-2 text-caption text-ink-soft break-words">Reply: {row.freelancer_reply}</p>
                  )}
                  {removed && row.removed_reason && (
                    <p className="mt-2 text-caption text-coral-ink">Removed: {row.removed_reason}</p>
                  )}
                </Cell>
                <Cell>
                  <Link to={`/admin/users/${row.freelancer.id}`} className="font-semibold text-primary hover:underline">
                    {row.freelancer.full_name}
                  </Link>
                </Cell>
                <Cell>
                  <Link to={`/admin/users/${row.client.id}`} className="hover:underline">
                    {row.client.full_name}
                  </Link>
                  <Link to={`/admin/gigs/${row.gig.id}`} className="block text-caption text-muted hover:underline">
                    {row.gig.title}
                  </Link>
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
        title="Remove this review?"
        description={pending && `${describe(pending.row)} will be hidden and will stop counting towards their rating. Both people are told, with your reason.`}
        confirmLabel="Remove review"
        reasonHint="The client and the freelancer both see this."
        onConfirm={moderation.confirm}
        onCancel={moderation.cancel}
      />
      <ConfirmDialog
        open={pending?.kind === 'restore'}
        title="Restore this review?"
        description={pending && `${describe(pending.row)} will be shown again and count towards their rating.`}
        confirmLabel="Restore review"
        reasonRequired={false}
        onConfirm={moderation.confirm}
        onCancel={moderation.cancel}
      />
    </>
  )
}
