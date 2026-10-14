import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { fetchGigApplicants, updateApplicationStatus } from '../../api/applications'
import { fetchGig } from '../../api/gigs'
import Alert from '../../components/Alert'
import ApplicantCard from '../../components/applications/ApplicantCard'
import ApplicationRowSkeleton from '../../components/applications/ApplicationRowSkeleton'
import StatusTabs, { STATUSES } from '../../components/applications/StatusTabs'
import Button from '../../components/Button'
import { STATUS_INFO } from '../../utils/applicationStatus'

export default function GigApplicants() {
  const { id } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const [gig, setGig] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadTick, setReloadTick] = useState(0)

  const requested = searchParams.get('status')
  const status = STATUSES.includes(requested) ? requested : ''
  const page = Math.max(1, Number.parseInt(searchParams.get('page'), 10) || 1)

  useEffect(() => {
    fetchGig(id)
      .then(setGig)
      .catch(() => {})
  }, [id])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    const params = { page }
    if (status) params.status = status
    fetchGigApplicants(id, params)
      .then((data) => {
        if (!cancelled) setResult(data)
      })
      .catch((err) => {
        if (cancelled) return
        if (err.response?.status === 404 && page > 1) {
          const next = new URLSearchParams(searchParams)
          next.delete('page')
          setSearchParams(next, { replace: true })
          return
        }
        if (err.response?.status === 403) setError('forbidden')
        else if (err.response?.status === 404) setError('missing')
        else setError('failed')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id, status, page, reloadTick])

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

  // After a change the list is loaded again, so the counts and the filtered tab stay true.
  const handleChangeStatus = async (application, nextStatus, note) => {
    await updateApplicationStatus(application.id, nextStatus, note)
    setReloadTick((n) => n + 1)
    fetchGig(id)
      .then(setGig)
      .catch(() => {})
  }

  if (error === 'forbidden') return <Alert type="error">You can only see applicants for your own gigs.</Alert>
  if (error === 'missing') return <Alert type="error">This gig does not exist.</Alert>

  const counts = result?.status_counts
  const hasNone = counts?.total === 0

  return (
    <div className="max-w-[960px]">
      <Link to="/gigs/mine" className="inline-block text-body text-primary font-medium mb-4">
        Back to My Gigs
      </Link>
      <h1 className="text-page-title text-primary mb-1">Applicants</h1>
      {gig && (
        <p className="text-body text-muted mb-6">
          <Link to={`/gigs/${gig.id}`} className="text-primary font-medium">
            {gig.title}
          </Link>
          {' · '}
          {STATUS_LABELS[gig.status] ?? gig.status}
        </p>
      )}

      <StatusTabs value={status} counts={counts} onSelect={selectStatus} />

      {error === 'failed' && (
        <div className="mb-4">
          <Alert type="error">
            Could not load the applicants.{' '}
            <button type="button" onClick={() => setReloadTick((n) => n + 1)} className="underline font-medium">
              Retry
            </button>
          </Alert>
        </div>
      )}

      {loading && !result && (
        <ul className="space-y-3" aria-label="Loading applicants">
          {Array.from({ length: 3 }).map((_, i) => (
            <ApplicationRowSkeleton key={i} />
          ))}
        </ul>
      )}

      {!error && result && result.results.length === 0 && (
        <div className="text-center py-16 border border-dashed border-border rounded-xl">
          {hasNone ? (
            <>
              <p className="text-section-title text-ink mb-2">No one has applied yet</p>
              <p className="text-body text-muted">Applicants show up here as soon as they apply.</p>
            </>
          ) : (
            <>
              <p className="text-section-title text-ink mb-2">
                No {status ? STATUS_INFO[status].label.toLowerCase() : ''} applicants
              </p>
              <Button variant="secondary" onClick={() => selectStatus('')}>
                Show all applicants
              </Button>
            </>
          )}
        </div>
      )}

      {!error && result && result.results.length > 0 && (
        <ul className={`space-y-4 transition-opacity ${loading ? 'opacity-50 pointer-events-none' : ''}`}>
          {result.results.map((application) => (
            <ApplicantCard key={application.id} application={application} onChangeStatus={handleChangeStatus} />
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

const STATUS_LABELS = {
  open: 'Open',
  in_progress: 'In progress',
  completed: 'Completed',
  closed: 'Closed',
}
