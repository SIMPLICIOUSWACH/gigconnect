import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, SlidersHorizontal, X } from 'lucide-react'
import { fetchSkills } from '../../api/auth'
import { fetchCategories, fetchGigsPaged } from '../../api/gigs'
import { useAuth } from '../../context/AuthContext'
import { RECOMMENDATIONS_ENABLED } from '../../constants'
import useCounties from '../../hooks/useCounties'
import useDebouncedValue from '../../hooks/useDebouncedValue'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import FilterDrawer from '../../components/gigs/FilterDrawer'
import FilterSidebar from '../../components/gigs/FilterSidebar'
import GigCard from '../../components/gigs/GigCard'
import GigCardSkeleton from '../../components/gigs/GigCardSkeleton'

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest' },
  { value: 'deadline', label: 'Deadline soonest' },
  { value: 'budget_high', label: 'Budget: high to low' },
  { value: 'budget_low', label: 'Budget: low to high' },
  { value: 'relevance', label: 'Best match' },
]

const POSTED_WITHIN_LABELS = {
  1: 'Last 24 hours',
  7: 'Last 7 days',
  30: 'Last 30 days',
}

function paramsToFilters(searchParams) {
  return {
    q: searchParams.get('q') || '',
    category: searchParams.get('category') || '',
    skillIds: (searchParams.get('skills') || '').split(',').filter(Boolean),
    budget_min: searchParams.get('budget_min') || '',
    budget_max: searchParams.get('budget_max') || '',
    negotiable: searchParams.get('negotiable') === 'true',
    includeClosed: searchParams.get('include_closed') === 'true',
    county: searchParams.get('county') || '',
    remote: searchParams.get('remote') === 'true',
    deadline_before: searchParams.get('deadline_before') || '',
    posted_within: searchParams.get('posted_within') || '',
    sort: searchParams.get('sort') || 'newest',
    page: Number(searchParams.get('page') || '1'),
  }
}

function formatApiError(data) {
  if (!data || typeof data !== 'object') return 'Could not load gigs. Please try again.'
  return Object.values(data).flat().join(' ')
}

function buildChips(filters, categories, skills, onChange) {
  const chips = []

  if (filters.q) {
    chips.push({ key: 'q', label: `Search: "${filters.q}"`, onRemove: () => onChange({ q: '' }) })
  }
  if (filters.category) {
    const cat = categories.find((c) => c.slug === filters.category)
    chips.push({ key: 'category', label: cat ? cat.name : filters.category, onRemove: () => onChange({ category: '' }) })
  }
  filters.skillIds.forEach((skillId) => {
    const skill = skills.find((s) => s.id === skillId)
    if (!skill) return
    chips.push({
      key: `skill-${skillId}`,
      label: skill.name,
      onRemove: () => onChange({ skillIds: filters.skillIds.filter((id) => id !== skillId) }),
    })
  })
  if (filters.budget_min || filters.budget_max) {
    const label =
      filters.budget_min && filters.budget_max
        ? `KES ${filters.budget_min}–${filters.budget_max}`
        : filters.budget_min
          ? `Min KES ${filters.budget_min}`
          : `Max KES ${filters.budget_max}`
    chips.push({ key: 'budget', label, onRemove: () => onChange({ budget_min: '', budget_max: '' }) })
  }
  if (filters.negotiable) {
    chips.push({ key: 'negotiable', label: 'Negotiable only', onRemove: () => onChange({ negotiable: false }) })
  }
  if (filters.county) {
    chips.push({ key: 'county', label: filters.county, onRemove: () => onChange({ county: '' }) })
  }
  if (filters.remote) {
    chips.push({ key: 'remote', label: 'Remote only', onRemove: () => onChange({ remote: false }) })
  }
  if (filters.includeClosed) {
    chips.push({
      key: 'include_closed',
      label: 'Including closed gigs',
      onRemove: () => onChange({ includeClosed: false }),
    })
  }
  if (filters.deadline_before) {
    chips.push({
      key: 'deadline_before',
      label: `Before ${filters.deadline_before}`,
      onRemove: () => onChange({ deadline_before: '' }),
    })
  }
  if (filters.posted_within) {
    chips.push({
      key: 'posted_within',
      label: POSTED_WITHIN_LABELS[filters.posted_within] || filters.posted_within,
      onRemove: () => onChange({ posted_within: '' }),
    })
  }

  return chips
}

export default function BrowseGigs() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = useMemo(() => paramsToFilters(searchParams), [searchParams])

  const [searchInput, setSearchInput] = useState(filters.q)
  const debouncedSearch = useDebouncedValue(searchInput, 400)

  const [categories, setCategories] = useState([])
  const counties = useCounties()
  const [skills, setSkills] = useState([])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState('')
  const [retryTick, setRetryTick] = useState(0)
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false)

  const filtersButtonRef = useRef(null)
  const closeFilters = useCallback(() => setMobileFiltersOpen(false), [])
  const requestIdRef = useRef(0)
  const hasLoadedRef = useRef(false)

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => setCategories([]))
    fetchSkills().then(setSkills).catch(() => setSkills([]))
  }, [])

  // Reflect a settled search box value into the URL, 400ms after the user stops typing.
  useEffect(() => {
    if (debouncedSearch === filters.q) return
    updateParams({ q: debouncedSearch }, { resetPage: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch])

  // Keep the search box in sync when the URL changes some other way (back/forward, chip removal).
  useEffect(() => {
    setSearchInput(filters.q)
  }, [filters.q])

  const updateParams = useCallback(
    (updates, { resetPage = false } = {}) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        const merged = { ...updates }

        // "Best match" only means anything with a query — drop a stale relevance sort
        // rather than let the backend silently reinterpret it as "newest" behind the UI's back.
        const nextQ = 'q' in merged ? merged.q : next.get('q')
        const nextSort = 'sort' in merged ? merged.sort : next.get('sort')
        if (!nextQ && nextSort === 'relevance') merged.sort = ''

        Object.entries(merged).forEach(([key, value]) => {
          if (!value) next.delete(key)
          else next.set(key, value === true ? 'true' : String(value))
        })
        if (resetPage) next.delete('page')
        return next
      })
    },
    [setSearchParams]
  )

  const PARAM_KEY_MAP = { skillIds: 'skills', includeClosed: 'include_closed' }

  const handleFilterChange = (updates) => {
    const mapped = {}
    Object.entries(updates).forEach(([key, value]) => {
      const paramKey = PARAM_KEY_MAP[key] || key
      mapped[paramKey] = key === 'skillIds' ? value.join(',') : value
    })
    updateParams(mapped, { resetPage: true })
  }

  const handleClearAll = () => {
    setSearchInput('')
    setSearchParams(new URLSearchParams())
  }

  const goToPage = (page) => updateParams({ page })

  useEffect(() => {
    const myRequestId = ++requestIdRef.current
    if (!hasLoadedRef.current) setLoading(true)
    else setFetching(true)
    setError('')

    const params = { page: filters.page }
    if (filters.q) params.q = filters.q
    if (filters.category) params.category = filters.category
    if (filters.skillIds.length) params.skills = filters.skillIds.join(',')
    if (filters.budget_min) params.budget_min = filters.budget_min
    if (filters.budget_max) params.budget_max = filters.budget_max
    if (filters.negotiable) params.negotiable = 'true'
    if (filters.includeClosed) params.include_closed = 'true'
    if (filters.county) params.county = filters.county
    if (filters.remote) params.remote = 'true'
    if (filters.deadline_before) params.deadline_before = filters.deadline_before
    if (filters.posted_within) params.posted_within = filters.posted_within
    if (filters.sort) params.sort = filters.sort

    fetchGigsPaged(params)
      .then((data) => {
        if (myRequestId !== requestIdRef.current) return
        setResult(data)
        hasLoadedRef.current = true
      })
      .catch((err) => {
        if (myRequestId !== requestIdRef.current) return
        setError(formatApiError(err.response?.data))
      })
      .finally(() => {
        if (myRequestId !== requestIdRef.current) return
        setLoading(false)
        setFetching(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    filters.q,
    filters.category,
    filters.skillIds.join(','),
    filters.budget_min,
    filters.budget_max,
    filters.negotiable,
    filters.includeClosed,
    filters.county,
    filters.remote,
    filters.deadline_before,
    filters.posted_within,
    filters.sort,
    filters.page,
    retryTick,
  ])

  const chips = buildChips(filters, categories, skills, handleFilterChange)

  return (
    <div className="max-w-[1200px]">
      <div className="mb-6">
        <h1 className="text-page-title text-primary mb-1">Browse Gigs</h1>
        <p className="text-body text-muted">Find work that matches your skills.</p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search gigs by title, skill, or description"
            aria-label="Search gigs"
            className="w-full pl-11 pr-4 py-3 border border-border rounded-lg text-body text-ink bg-surface placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
        </div>
        <select
          value={filters.sort}
          aria-label="Sort gigs"
          onChange={(e) => updateParams({ sort: e.target.value }, { resetPage: true })}
          className="px-4 py-3 border border-border rounded-lg text-body text-ink bg-surface focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors sm:w-56"
        >
          {SORT_OPTIONS.filter((opt) => opt.value !== 'relevance' || filters.q).map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <button
          ref={filtersButtonRef}
          type="button"
          aria-haspopup="dialog"
          aria-expanded={mobileFiltersOpen}
          onClick={() => setMobileFiltersOpen(true)}
          className="md:hidden inline-flex items-center justify-center gap-2 px-4 py-3 border border-border rounded-lg text-body text-ink bg-surface"
        >
          <SlidersHorizontal size={18} aria-hidden="true" />
          Filters
        </button>
      </div>

      <div className="flex gap-8">
        <aside className="hidden md:block w-[280px] shrink-0">
          <FilterSidebar
            categories={categories}
            counties={counties}
            skills={skills}
            filters={filters}
            onChange={handleFilterChange}
            onClear={handleClearAll}
          />
        </aside>

        <div className="flex-1 min-w-0">
          {chips.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-4">
              {chips.map((chip) => (
                <button
                  key={chip.key}
                  type="button"
                  onClick={chip.onRemove}
                  aria-label={`Remove filter: ${chip.label}`}
                  className="inline-flex items-center gap-1.5 text-caption font-medium px-3 py-1.5 rounded-full bg-primary-light text-primary"
                >
                  {chip.label}
                  <X size={13} aria-hidden="true" />
                </button>
              ))}
            </div>
          )}

          {error && (
            <div className="mb-4">
              <Alert type="error">
                {error}{' '}
                <button
                  type="button"
                  onClick={() => setRetryTick((t) => t + 1)}
                  className="font-medium underline"
                >
                  Retry
                </button>
              </Alert>
            </div>
          )}

          {/* Always rendered so screen readers register changes to it. */}
          <p
            role="status"
            aria-live="polite"
            className={error || !result ? 'sr-only' : 'text-caption text-muted mb-4'}
          >
            {error ? '' : result ? `${result.count} gig${result.count === 1 ? '' : 's'} found` : 'Loading gigs'}
          </p>

          {loading && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <GigCardSkeleton key={i} />
              ))}
            </div>
          )}

          {!loading && result && result.results.length === 0 && (
            <div className="text-center py-16 border border-dashed border-border rounded-xl">
              <p className="text-section-title text-ink mb-2">No gigs match your filters</p>
              <p className="text-body text-muted mb-4">
                {chips.length > 0
                  ? 'Try removing a filter or widening your search.'
                  : 'Check back soon — new gigs are posted regularly.'}
              </p>
              {chips.length > 0 && (
                <Button variant="secondary" onClick={handleClearAll}>
                  Clear all filters
                </Button>
              )}
            </div>
          )}

          {!loading && result && result.results.length > 0 && (
            <div
              className={`grid grid-cols-1 sm:grid-cols-2 gap-4 transition-opacity ${
                fetching ? 'opacity-50 pointer-events-none' : ''
              }`}
            >
              {result.results.map((gig, index) => (
                <GigCard
                  key={gig.id}
                  gig={gig}
                  query={filters.q}
                  position={(result.page - 1) * result.page_size + index + 1}
                />
              ))}
            </div>
          )}

          {result && result.total_pages > 1 && (
            <div className="flex items-center justify-between mt-8">
              <Button variant="secondary" disabled={!result.previous} onClick={() => goToPage(filters.page - 1)}>
                Previous
              </Button>
              <span className="text-body text-muted">
                Page {result.page} of {result.total_pages}
              </span>
              <Button variant="secondary" disabled={!result.next} onClick={() => goToPage(filters.page + 1)}>
                Next
              </Button>
            </div>
          )}

          {user?.role === 'freelancer' && (
            <div className="mt-12 pt-8 border-t border-border">
              <h2 className="text-section-title text-ink mb-2">Recommended for You</h2>
              {RECOMMENDATIONS_ENABLED ? null : (
                <p className="text-body text-muted">
                  We don't have personalized recommendations yet — that's coming in a future update.
                  Use search and filters above to find gigs that match your skills.
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      <FilterDrawer open={mobileFiltersOpen} onClose={closeFilters} returnFocusRef={filtersButtonRef}>
        <FilterSidebar
          categories={categories}
          counties={counties}
          skills={skills}
          filters={filters}
          onChange={handleFilterChange}
          onClear={handleClearAll}
        />
        <Button className="w-full mt-6" onClick={closeFilters}>
          Show results
        </Button>
      </FilterDrawer>
    </div>
  )
}
