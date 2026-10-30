import { Link } from 'react-router-dom'
import { fetchAuditLog } from '../api'
import {
  Cell,
  DataTable,
  EmptyRow,
  ErrorBox,
  Field,
  FilterBar,
  PageHeader,
  Pager,
  Pill,
  SkeletonRows,
  fieldClass,
} from '../components/ui'
import { ACTION_LABELS, NEGATIVE_ACTIONS, TARGET_TYPE_LABELS, formatDateTime, targetPath } from '../format'
import { useAdminData } from '../useAdminData'
import { useUrlFilters } from '../useUrlFilters'

const COLUMNS = ['When', 'Admin', 'Action', 'Target', 'Reason']

export default function AuditLogPage() {
  const { filters, page, setFilter, setPage, key } = useUrlFilters(['action', 'target_type', 'admin'])
  const { data, error, loading, reload } = useAdminData(() => fetchAuditLog({ ...filters, page }), key)

  return (
    <>
      <PageHeader title="Audit log">Every change an admin has made, newest first. Entries can't be edited or deleted.</PageHeader>

      <FilterBar>
        <Field label="Action">
          <select value={filters.action} onChange={(e) => setFilter('action', e.target.value)} className={fieldClass}>
            <option value="">All actions</option>
            {Object.entries(ACTION_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Target">
          <select value={filters.target_type} onChange={(e) => setFilter('target_type', e.target.value)} className={fieldClass}>
            <option value="">Users, gigs and applications</option>
            {Object.entries(TARGET_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}s
              </option>
            ))}
          </select>
        </Field>
        {filters.admin && (
          <div className="self-end">
            <button type="button" onClick={() => setFilter('admin', '')} className="text-label text-primary underline min-h-[44px]">
              Show every admin&apos;s actions
            </button>
          </div>
        )}
      </FilterBar>

      {error && <ErrorBox onRetry={reload}>{error}</ErrorBox>}

      <DataTable caption="Audit log" columns={COLUMNS}>
        {loading && !data ? (
          <SkeletonRows columns={COLUMNS.length} />
        ) : data?.results.length === 0 ? (
          <EmptyRow columns={COLUMNS.length}>No admin actions yet.</EmptyRow>
        ) : (
          data?.results.map((row) => (
            <tr key={row.id}>
              <Cell className="whitespace-nowrap">{formatDateTime(row.created_at)}</Cell>
              <Cell>
                {row.admin ? (
                  <button type="button" onClick={() => setFilter('admin', row.admin.id)} className="text-left hover:underline">
                    {row.admin.full_name}
                  </button>
                ) : (
                  <span className="text-muted">A removed admin</span>
                )}
              </Cell>
              <Cell>
                <Pill tone={NEGATIVE_ACTIONS.has(row.action) ? 'coral' : 'mint'}>{ACTION_LABELS[row.action]}</Pill>
              </Cell>
              <Cell>
                <span className="block text-caption text-muted">{TARGET_TYPE_LABELS[row.target_type]}</span>
                <Link to={targetPath(row)} className="text-primary font-semibold hover:underline">
                  {row.target_label || `Deleted ${TARGET_TYPE_LABELS[row.target_type].toLowerCase()}`}
                </Link>
              </Cell>
              <Cell className="max-w-[360px] break-words">{row.reason || <span className="text-muted">No reason given</span>}</Cell>
            </tr>
          ))
        )}
      </DataTable>
      <Pager data={data} page={page} onPage={setPage} />
    </>
  )
}
