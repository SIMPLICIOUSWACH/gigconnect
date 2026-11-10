import { Link } from 'react-router-dom'
import { fetchChatReports } from '../api'
import { Cell, DataTable, EmptyRow, ErrorBox, PageHeader, Pager, Pill, SkeletonRows } from '../components/ui'
import { formatDateTime } from '../format'
import { useAdminData } from '../useAdminData'
import { useUrlFilters } from '../useUrlFilters'

const COLUMNS = ['Reported', 'Chat', 'Reported by', 'Reason', 'Status', '']
const TABS = [
  { value: '', label: 'Open' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'all', label: 'All' },
]

const tab = (active) =>
  `min-h-[40px] px-4 rounded-pill text-nav ${active ? 'bg-ink text-white font-semibold' : 'bg-surface text-ink-soft shadow-ring-border hover:bg-sand'}`

export default function ChatReportsPage() {
  const { filters, page, setFilter, setPage, key } = useUrlFilters(['status', 'conversation'])
  const { data, error, loading, reload } = useAdminData(
    () => fetchChatReports({ status: filters.status || 'open', conversation: filters.conversation, page }),
    key
  )

  return (
    <>
      <PageHeader title="Reported chats">
        Chats are private. You can only read one that a participant reported, and every time you open it, that is
        recorded in the audit log.
      </PageHeader>

      <div className="flex flex-wrap gap-2 mb-4" role="group" aria-label="Show">
        {TABS.map((item) => (
          <button
            key={item.label}
            type="button"
            aria-pressed={filters.status === item.value}
            onClick={() => setFilter('status', item.value)}
            className={tab(filters.status === item.value)}
          >
            {item.label}
          </button>
        ))}
        {filters.conversation && (
          <button
            type="button"
            onClick={() => setFilter('conversation', '')}
            className="inline-flex items-center gap-2 text-label bg-ink text-white px-3 py-1.5 rounded-pill"
          >
            One chat
            <span aria-hidden="true">×</span>
            <span className="sr-only">, show every chat instead</span>
          </button>
        )}
      </div>

      {error && <ErrorBox onRetry={reload}>{error}</ErrorBox>}

      <DataTable caption="Reported chats" columns={COLUMNS}>
        {loading && !data ? (
          <SkeletonRows columns={COLUMNS.length} />
        ) : data?.results.length === 0 ? (
          <EmptyRow columns={COLUMNS.length}>
            {filters.status ? 'No reports here.' : 'No open reports. Nothing needs looking at.'}
          </EmptyRow>
        ) : (
          data?.results.map((row) => (
            <tr key={row.id} className="hover:bg-sand/60">
              <Cell className="whitespace-nowrap">{formatDateTime(row.created_at)}</Cell>
              <Cell>
                <span className="font-semibold text-ink">
                  {row.client.full_name} and {row.freelancer.full_name}
                </span>
                <span className="block text-caption text-muted">{row.gig.title}</span>
              </Cell>
              <Cell>{row.reporter.full_name}</Cell>
              <Cell className="max-w-[320px]">
                <p className="line-clamp-2 break-words">{row.reason}</p>
              </Cell>
              <Cell>{row.resolved_at ? <Pill tone="mint">Resolved</Pill> : <Pill tone="sun">Open</Pill>}</Cell>
              <Cell>
                <Link to={`/admin/chat-reports/${row.id}`} className="font-semibold text-primary hover:underline whitespace-nowrap">
                  Open chat
                  <span className="sr-only">
                    {' '}
                    between {row.client.full_name} and {row.freelancer.full_name}
                  </span>
                </Link>
              </Cell>
            </tr>
          ))
        )}
      </DataTable>
      <Pager data={data} page={page} onPage={setPage} />
    </>
  )
}
