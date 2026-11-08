import { useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchUsers } from '../api'
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
  primaryButton,
} from '../components/ui'
import { ACCOUNT_STATUS, ROLE_LABELS, VERIFICATION, formatDate } from '../format'
import { useAdminData } from '../useAdminData'
import { useUrlFilters } from '../useUrlFilters'

const COLUMNS = ['Name', 'Email', 'Role', 'Verified', 'Status', 'Joined']

export default function UsersPage() {
  const { filters, page, setFilter, setPage, key } = useUrlFilters(['search', 'role', 'status', 'verified'])
  const [search, setSearch] = useState(filters.search)
  const { data, error, loading, reload } = useAdminData(() => fetchUsers({ ...filters, page }), key)

  return (
    <>
      <PageHeader title="Users">Everyone with a GigConnect account. Open a user to see their gigs, applications and history.</PageHeader>

      <FilterBar onSubmit={() => setFilter('search', search.trim())}>
        <Field label="Search name or email">
          <span className="flex gap-2">
            <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} className={fieldClass} />
            <button type="submit" className={primaryButton}>
              Search
            </button>
          </span>
        </Field>
        <Field label="Role">
          <select value={filters.role} onChange={(e) => setFilter('role', e.target.value)} className={fieldClass}>
            <option value="">All roles</option>
            <option value="freelancer">Freelancers</option>
            <option value="client">Clients</option>
            <option value="admin">Admins</option>
          </select>
        </Field>
        <Field label="Status">
          <select value={filters.status} onChange={(e) => setFilter('status', e.target.value)} className={fieldClass}>
            <option value="">Any status</option>
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
            <option value="deleted">Deleted</option>
          </select>
        </Field>
        <Field label="ID verified">
          <select value={filters.verified} onChange={(e) => setFilter('verified', e.target.value)} className={fieldClass}>
            <option value="">Either</option>
            <option value="true">Verified</option>
            <option value="false">Not verified</option>
          </select>
        </Field>
      </FilterBar>

      {error && <ErrorBox onRetry={reload}>{error}</ErrorBox>}
      {data && <p className="text-caption text-muted mb-2">{data.count} {data.count === 1 ? 'user' : 'users'}</p>}

      <DataTable caption="Users" columns={COLUMNS}>
        {loading && !data ? (
          <SkeletonRows columns={COLUMNS.length} />
        ) : data?.results.length === 0 ? (
          <EmptyRow columns={COLUMNS.length}>No users match these filters.</EmptyRow>
        ) : (
          data?.results.map((user) => {
            const status = ACCOUNT_STATUS[user.status]
            const verification = VERIFICATION[user.verification_status]
            return (
              <tr key={user.id} className="hover:bg-sand/60">
                <Cell>
                  <Link to={`/admin/users/${user.id}`} className="font-semibold text-primary hover:underline">
                    {user.full_name || 'No name given'}
                  </Link>
                  {user.is_synthetic && <span className="block text-caption text-muted">Synthetic</span>}
                </Cell>
                <Cell className="break-all">{user.email}</Cell>
                <Cell>{ROLE_LABELS[user.role]}</Cell>
                <Cell>{verification ? <Pill tone={verification.tone}>{verification.label}</Pill> : <span className="text-muted">Not applicable</span>}</Cell>
                <Cell>
                  <Pill tone={status.tone}>{status.label}</Pill>
                </Cell>
                <Cell className="whitespace-nowrap">{formatDate(user.created_at)}</Cell>
              </tr>
            )
          })
        )}
      </DataTable>
      <Pager data={data} page={page} onPage={setPage} />
    </>
  )
}
