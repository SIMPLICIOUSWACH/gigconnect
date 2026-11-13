import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import { fetchSkills } from '../../api/auth'
import { searchFreelancers } from '../../api/freelancers'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import FreelancerCard from '../../components/freelancers/FreelancerCard'
import InviteDialog from '../../components/freelancers/InviteDialog'
import { useAuth } from '../../context/AuthContext'
import useCounties from '../../hooks/useCounties'

const SORTS = [
  { value: 'best_match', label: 'Best match' },
  { value: 'rating', label: 'Highest rated' },
  { value: 'completed', label: 'Most gigs completed' },
  { value: 'newest', label: 'Newest' },
]
const RATINGS = [
  { value: '', label: 'Any rating' },
  { value: '3', label: '3 stars and up' },
  { value: '4', label: '4 stars and up' },
  { value: '4.5', label: '4.5 stars and up' },
]
const TOGGLES = [
  { key: 'remote', label: 'Open to remote' },
  { key: 'verified', label: 'Verified ID only' },
  { key: 'available', label: 'Available now' },
]

// The filters live in the URL, like Find gigs, so a search can be bookmarked, shared and gone back to.
function paramsToFilters(params) {
  return {
    q: params.get('q') || '',
    skillIds: (params.get('skills') || '').split(',').filter(Boolean),
    county: params.get('county') || '',
    remote: params.get('remote') === 'true',
    verified: params.get('verified') === 'true',
    available: params.get('available') === 'true',
    min_rating: params.get('min_rating') || '',
    sort: params.get('sort') || 'best_match',
  }
}

function apiParams(filters, page) {
  const params = { page }
  if (filters.q) params.q = filters.q
  if (filters.skillIds.length) params.skills = filters.skillIds.join(',')
  if (filters.county) params.county = filters.county
  TOGGLES.forEach(({ key }) => {
    if (filters[key]) params[key] = 'true'
  })
  if (filters.min_rating) params.min_rating = filters.min_rating
  if (filters.sort !== 'best_match') params.sort = filters.sort
  return params
}

const field =
  'min-h-[44px] rounded-input border border-border bg-surface px-3 text-[15px] text-ink focus:outline-none focus:ring-2 focus:ring-primary'

function pillClass(pressed) {
  return `min-h-[40px] px-4 rounded-pill text-[14px] transition-colors ${
    pressed ? 'bg-ink text-white font-semibold' : 'bg-surface text-ink font-medium border border-border hover:bg-sand'
  }`
}

function CardSkeleton() {
  return <li aria-hidden="true" className="h-64 rounded-card bg-track animate-pulse" />
}

export default function FindFreelancers() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const filterKey = searchParams.toString()
  const filters = useMemo(() => paramsToFilters(new URLSearchParams(filterKey)), [filterKey])
  const [searchInput, setSearchInput] = useState(filters.q)
  const [skills, setSkills] = useState([])
  const counties = useCounties()
  // What is on screen: the freelancers loaded so far, the total, and the last page fetched.
  const [list, setList] = useState({ results: [], count: 0, page: 0, totalPages: 0 })
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [inviting, setInviting] = useState(null)
  const [notice, setNotice] = useState('')
  const canInvite = user?.role === 'client'

  useEffect(() => {
    fetchSkills().then(setSkills).catch(() => setSkills([]))
  }, [])

  useEffect(() => {
    setSearchInput(filters.q)
  }, [filters.q])

  // A new search or filter starts again from page 1.
  useEffect(() => {
    let alive = true
    setLoading(true)
    setError('')
    searchFreelancers(apiParams(filters, 1))
      .then((data) => {
        if (!alive) return
        setList({ results: data.results, count: data.count, page: 1, totalPages: data.total_pages })
      })
      .catch((err) => {
        if (!alive) return
        setList({ results: [], count: 0, page: 0, totalPages: 0 })
        setError(
          err?.response?.status === 429
            ? 'You are searching very quickly. Wait a moment and try again.'
            : 'Could not load freelancers. Try again.'
        )
      })
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [filters])

  const update = (changes) => {
    const next = new URLSearchParams(searchParams)
    Object.entries(changes).forEach(([key, value]) => {
      const text = Array.isArray(value) ? value.join(',') : value === true ? 'true' : value || ''
      if (text && !(key === 'sort' && text === 'best_match')) next.set(key, text)
      else next.delete(key)
    })
    setSearchParams(next)
  }

  const submitSearch = (e) => {
    e.preventDefault()
    update({ q: searchInput.trim() })
  }

  const loadMore = async () => {
    setLoadingMore(true)
    setError('')
    try {
      const data = await searchFreelancers(apiParams(filters, list.page + 1))
      setList((current) => ({
        results: [...current.results, ...data.results],
        count: data.count,
        page: data.page,
        totalPages: data.total_pages,
      }))
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not load more freelancers. Try again.')
    } finally {
      setLoadingMore(false)
    }
  }

  const skillName = (id) => skills.find((skill) => String(skill.id) === id)?.name || 'Skill'
  const chips = [
    filters.q && { key: 'q', label: `"${filters.q}"`, clear: { q: '' } },
    ...filters.skillIds.map((id) => ({
      key: `skill-${id}`,
      label: skillName(id),
      clear: { skills: filters.skillIds.filter((other) => other !== id) },
    })),
    filters.county && { key: 'county', label: filters.county, clear: { county: '' } },
    filters.min_rating && { key: 'rating', label: `${filters.min_rating} stars and up`, clear: { min_rating: '' } },
    ...TOGGLES.filter(({ key }) => filters[key]).map(({ key, label }) => ({ key, label, clear: { [key]: '' } })),
  ].filter(Boolean)

  const clearAll = () => setSearchParams(filters.sort === 'best_match' ? {} : { sort: filters.sort })

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-page-title text-ink">Find freelancers</h1>
        <p className="text-body text-ink-soft mt-1">
          Search by name, skill or what they do, then invite someone to apply to one of your open gigs.
        </p>
      </div>

      <form onSubmit={submitSearch} role="search" className="flex flex-wrap gap-2">
        <label htmlFor="freelancer-search" className="sr-only">
          Search freelancers
        </label>
        <div className="relative flex-1 min-w-[220px]">
          <Search size={18} aria-hidden="true" className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" />
          <input
            id="freelancer-search"
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            maxLength={100}
            placeholder="Try &quot;logo design&quot; or &quot;plumber&quot;"
            className={`${field} w-full pl-10`}
          />
        </div>
        <Button type="submit">Search</Button>
      </form>

      <div className="bg-surface rounded-card shadow-hairline p-4 flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="flex flex-col gap-1 text-label text-ink">
            Skill
            <select
              value=""
              onChange={(e) => e.target.value && update({ skills: [...new Set([...filters.skillIds, e.target.value])] })}
              className={field}
            >
              <option value="">Add a skill</option>
              {skills
                .filter((skill) => !filters.skillIds.includes(String(skill.id)))
                .map((skill) => (
                  <option key={skill.id} value={skill.id}>
                    {skill.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-label text-ink">
            County
            <select value={filters.county} onChange={(e) => update({ county: e.target.value })} className={field}>
              <option value="">Any county</option>
              {counties.map((county) => (
                <option key={county.value} value={county.value}>
                  {county.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-label text-ink">
            Minimum rating
            <select value={filters.min_rating} onChange={(e) => update({ min_rating: e.target.value })} className={field}>
              {RATINGS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-label text-ink">
            Sort by
            <select value={filters.sort} onChange={(e) => update({ sort: e.target.value })} className={field}>
              {SORTS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div role="group" aria-label="More filters" className="flex flex-wrap gap-2">
          {TOGGLES.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              aria-pressed={filters[key]}
              onClick={() => update({ [key]: !filters[key] })}
              className={pillClass(filters[key])}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {chips.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {chips.map((chip) => (
            <button
              key={chip.key}
              type="button"
              onClick={() => update(chip.clear)}
              aria-label={`Remove filter: ${chip.label}`}
              className="inline-flex items-center gap-1.5 text-caption font-semibold px-3 py-1.5 rounded-pill bg-primary-light text-primary"
            >
              {chip.label}
              <X size={13} aria-hidden="true" />
            </button>
          ))}
          <button type="button" onClick={clearAll} className="text-caption font-semibold text-ink-soft underline px-2">
            Clear all
          </button>
        </div>
      )}

      {notice && (
        <div role="status">
          <Alert type="success">{notice}</Alert>
        </div>
      )}
      {error && <Alert type="error">{error}</Alert>}

      <p className="text-caption text-muted" aria-live="polite">
        {loading ? 'Searching…' : `${list.count} ${list.count === 1 ? 'freelancer' : 'freelancers'}`}
      </p>

      {loading ? (
        <ul aria-label="Loading freelancers" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </ul>
      ) : list.results.length === 0 && !error ? (
        <div className="text-center py-14 px-4 border border-dashed border-divider rounded-card">
          <p className="text-section-title text-ink">No freelancers match</p>
          <p className="text-body text-muted mt-1">
            {chips.length > 0 ? 'Try fewer filters or a different word.' : 'Nobody is listed yet.'}
          </p>
        </div>
      ) : (
        <ul aria-label="Freelancers" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {list.results.map((freelancer) => (
            <li key={freelancer.id}>
              <FreelancerCard
                freelancer={freelancer}
                action={
                  canInvite && (
                    <button
                      type="button"
                      onClick={() => setInviting(freelancer)}
                      className="inline-flex items-center justify-center min-h-[40px] px-4 rounded-button text-[14px] font-bold bg-primary text-white hover:bg-primary-hover"
                    >
                      Invite to apply
                      <span className="sr-only"> {freelancer.full_name}</span>
                    </button>
                  )
                }
              />
            </li>
          ))}
        </ul>
      )}

      {!loading && list.page < list.totalPages && (
        <div className="text-center">
          <Button variant="secondary" onClick={loadMore} loading={loadingMore}>
            Load more freelancers
          </Button>
        </div>
      )}

      {inviting && (
        <InviteDialog
          freelancer={inviting}
          onClose={() => setInviting(null)}
          onInvited={(result) => {
            setInviting(null)
            setNotice(result.detail)
          }}
        />
      )}
    </div>
  )
}
