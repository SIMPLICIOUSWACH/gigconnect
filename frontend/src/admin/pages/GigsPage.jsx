import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchCategories, fetchGigs, removeGig, restoreGig } from '../api'
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
  primaryButton,
  quietButton,
} from '../components/ui'
import { GIG_STATUS, formatBudget, formatDate } from '../format'
import { useAdminData, withRow } from '../useAdminData'
import { useModeration } from '../useModeration'
import { useUrlFilters } from '../useUrlFilters'

const COLUMNS = ['Gig', 'Client', 'Category', 'Status', 'Applications', 'Posted', 'Action']

export function GigModerationDialogs({ moderation }) {
  const { pending } = moderation
  return (
    <>
      <ConfirmDialog
        open={pending?.kind === 'remove'}
        title={`Remove "${pending?.row.title}"?`}
        description="Freelancers stop seeing it at once, in the feed, search and recommendations. The client sees it marked removed and can't edit it. You can restore it later."
        confirmLabel="Remove gig"
        onConfirm={moderation.confirm}
        onCancel={moderation.cancel}
      />
      <ConfirmDialog
        open={pending?.kind === 'restore'}
        title={`Restore "${pending?.row.title}"?`}
        description="It goes back to how it was before it was removed."
        confirmLabel="Restore gig"
        reasonRequired={false}
        onConfirm={moderation.confirm}
        onCancel={moderation.cancel}
      />
    </>
  )
}

export default function GigsPage() {
  const { filters, page, setFilter, setPage, key } = useUrlFilters(['search', 'status', 'category', 'moderation'])
  const [search, setSearch] = useState(filters.search)
  const [categories, setCategories] = useState([])
  const { data, setData, error, loading, reload } = useAdminData(() => fetchGigs({ ...filters, page }), key)
  const moderation = useModeration({
    remove: removeGig,
    restore: restoreGig,
    onUpdated: (row) => setData((current) => withRow(current, row)),
    describe: (row) => `"${row.title}"`,
  })

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => setCategories([]))
  }, [])

  return (
    <>
      <PageHeader title="Gigs">Every gig, whatever its status. Removing a gig hides it from freelancers; restoring brings it back.</PageHeader>

      <FilterBar onSubmit={() => setFilter('search', search.trim())}>
        <Field label="Search title or client">
          <span className="flex gap-2">
            <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} className={fieldClass} />
            <button type="submit" className={primaryButton}>
              Search
            </button>
          </span>
        </Field>
        <Field label="Status">
          <select value={filters.status} onChange={(e) => setFilter('status', e.target.value)} className={fieldClass}>
            <option value="">Any status</option>
            {Object.entries(GIG_STATUS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Category">
          <select value={filters.category} onChange={(e) => setFilter('category', e.target.value)} className={fieldClass}>
            <option value="">All categories</option>
            {categories.map((category) => (
              <option key={category.slug} value={category.slug}>
                {category.name}
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

      {error && <ErrorBox onRetry={reload}>{error}</ErrorBox>}
      {data && <p className="text-caption text-muted mb-2">{data.count} {data.count === 1 ? 'gig' : 'gigs'}</p>}

      <DataTable caption="Gigs" columns={COLUMNS}>
        {loading && !data ? (
          <SkeletonRows columns={COLUMNS.length} />
        ) : data?.results.length === 0 ? (
          <EmptyRow columns={COLUMNS.length}>No gigs match these filters.</EmptyRow>
        ) : (
          data?.results.map((gig) => {
            const removed = gig.moderation_status === 'removed'
            return (
              <tr key={gig.id} className="hover:bg-sand/60">
                <Cell>
                  <Link to={`/admin/gigs/${gig.id}`} className="font-semibold text-primary hover:underline">
                    {gig.title}
                  </Link>
                  <span className="block text-caption text-muted">{formatBudget(gig)}</span>
                </Cell>
                <Cell>
                  <Link to={`/admin/users/${gig.client.id}`} className="hover:underline">
                    {gig.client.full_name}
                  </Link>
                  {gig.client_status === 'suspended' && <span className="block text-caption text-coral-ink">Suspended</span>}
                </Cell>
                <Cell>{gig.category}</Cell>
                <Cell>
                  <span className="flex flex-wrap gap-1.5 items-center">
                    {GIG_STATUS[gig.status]}
                    {removed && <RemovedPill />}
                  </span>
                </Cell>
                <Cell>{gig.application_count}</Cell>
                <Cell className="whitespace-nowrap">{formatDate(gig.created_at)}</Cell>
                <Cell>
                  {removed ? (
                    <button type="button" className={quietButton} onClick={() => moderation.askRestore(gig)}>
                      Restore
                      <span className="sr-only"> {gig.title}</span>
                    </button>
                  ) : (
                    <button type="button" className={dangerButton} onClick={() => moderation.askRemove(gig)}>
                      Remove
                      <span className="sr-only"> {gig.title}</span>
                    </button>
                  )}
                </Cell>
              </tr>
            )
          })
        )}
      </DataTable>
      <Pager data={data} page={page} onPage={setPage} />
      <GigModerationDialogs moderation={moderation} />
    </>
  )
}
