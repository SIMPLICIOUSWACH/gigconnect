import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchMyApplications } from '../../api/applications'
import Alert from '../../components/Alert'
import ApplicationRow from '../../components/applications/ApplicationRow'
import ApplicationRowSkeleton from '../../components/applications/ApplicationRowSkeleton'
import Button from '../../components/Button'
import { STATUS_INFO } from '../../utils/applicationStatus'

const STATUSES = Object.keys(STATUS_INFO)

// The boxes along the top, as in the proposal wireframe. Every number comes from the API.
const SUMMARY_BOXES = [
  { key: 'total', label: 'Total' },
  { key: 'pending', label: 'Pending' },
  { key: 'shortlisted', label: 'Shortlisted' },
  { key: 'hired', label: 'Hired' },
  { key: 'rejected', label: 'Not selected' },
]

export default function MyApplications() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [retryTick, setRetryTick] = useState(0)

  const requested = searchParams.get('status')
  const status = STATUSES.includes(requested) ? requested : ''
  const page = Math.max(1, Number.parseInt(searchParams.get('page'), 10) || 1)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    const params = { page }
    if (status) params.status = status
    fetchMyApplications(params)
      .then((data) => {
        if (!cancelled) setResult(data)
      })
      .catch((err) => {
        if (cancelled) return
        // A page number beyond the last page (an old link) is not an error: go back to page 1.
        if (err.response?.status === 404 && page > 1) {
          const params = new URLSearchParams(searchParams)
          params.delete('page')
          setSearchParams(params, { replace: true })
          return
        }
        setError(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [status, page, retryTick])

  const selectStatus = (next) => {
    const params = new URLSearchParams()
    if (next) params.set('status', next)
    setSearchParams(params)
  }

  const goToPage = (next) => {
    const params = new URLSearchParams(searchParams)
    if (next > 1) params.set('page', String(next))
    else params.delete('page')
    setSearchParams(params)
  }

  const counts = result?.status_counts
  const hasNone = counts?.total === 0

  return (
    <div className="max-w-[960px]">
      <h1 className="text-page-title text-primary mb-6">My Applications</h1>

      {counts && (
        <dl className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-8">
          {SUMMARY_BOXES.map((box) => (
            <div key={box.key} className="bg-surface border border-border rounded-xl p-4">
              <dt className="text-label text-muted">{box.label}</dt>
              <dd className="text-page-title text-ink">{counts[box.key] ?? 0}</dd>
            </div>
          ))}
        </dl>
      )}

      <nav aria-label="Filter applications by status" className="flex flex-wrap gap-2 mb-6">
        {[{ value: '', label: 'All' }, ...STATUSES.map((s) => ({ value: s, label: STATUS_INFO[s].label }))].map(
          (tab) => {
            const active = tab.value === status
            const count = counts ? (tab.value ? counts[tab.value] : counts.total) : null
            return (
              <button
                key={tab.value || 'all'}
                type="button"
                onClick={() => selectStatus(tab.value)}
                aria-current={active ? 'true' : undefined}
                className={`px-4 py-2 rounded-full text-nav transition-colors duration-150 border ${
                  active
                    ? 'bg-primary text-white border-primary'
                    : 'bg-surface text-muted border-border hover:text-ink hover:bg-bg'
                }`}
              >
                {tab.label}
                {count !== null && ` (${count})`}
              </button>
            )
          }
        )}
      </nav>

      {error && (
        <div className="mb-4">
          <Alert type="error">
            Could not load your applications.{' '}
            <button type="button" onClick={() => setRetryTick((n) => n + 1)} className="underline font-medium">
              Retry
            </button>
          </Alert>
        </div>
      )}

      {loading && !result && (
        <ul className="space-y-3" aria-label="Loading applications">
          {Array.from({ length: 4 }).map((_, i) => (
            <ApplicationRowSkeleton key={i} />
          ))}
        </ul>
      )}

      {!error && result && result.results.length === 0 && (
        <div className="text-center py-16 border border-dashed border-border rounded-xl">
          {hasNone ? (
            <>
              <p className="text-section-title text-ink mb-2">You haven't applied to any gigs yet</p>
              <p className="text-body text-muted mb-4">When you apply, your applications and their status show up here.</p>
              <Link to="/gigs">
                <Button>Browse gigs</Button>
              </Link>
            </>
          ) : (
            <>
              <p className="text-section-title text-ink mb-2">
                No {status ? STATUS_INFO[status].label.toLowerCase() : ''} applications
              </p>
              <Button variant="secondary" onClick={() => selectStatus('')}>
                Show all applications
              </Button>
            </>
          )}
        </div>
      )}

      {!error && result && result.results.length > 0 && (
        <ul className={`space-y-3 transition-opacity ${loading ? 'opacity-50 pointer-events-none' : ''}`}>
          {result.results.map((application) => (
            <ApplicationRow key={application.id} application={application} />
          ))}
        </ul>
      )}

      {!error && result && result.total_pages > 1 && (
        <div className="flex items-center justify-between mt-8">
          <Button variant="secondary" disabled={!result.previous} onClick={() => goToPage(page - 1)}>
            Previous
          </Button>
          <span className="text-body text-muted">
            Page {result.page} of {result.total_pages}
          </span>
          <Button variant="secondary" disabled={!result.next} onClick={() => goToPage(page + 1)}>
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
