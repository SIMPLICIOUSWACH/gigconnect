import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { SlidersHorizontal, X } from 'lucide-react'
import { fetchSkills } from '../../api/auth'
import { fetchCategories, fetchGigsPaged } from '../../api/gigs'
import { useAuth } from '../../context/AuthContext'
import useCounties from '../../hooks/useCounties'
import useDebouncedValue from '../../hooks/useDebouncedValue'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import BrowseHero from '../../components/gigs/BrowseHero'
import CategoryTiles from '../../components/gigs/CategoryTiles'
import FilterSidebar from '../../components/gigs/FilterSidebar'
import GigCard from '../../components/gigs/GigCard'
import GigCardSkeleton from '../../components/gigs/GigCardSkeleton'
import RecommendedForYou from '../../components/recommendations/RecommendedForYou'

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

const QUICK_BUDGET_MIN = '20000'

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
    urgent: searchParams.get('urgent') === 'true',
    deadline_before: searchParams.get('deadline_before') || '',
    posted_within: searchParams.get('posted_within') || '',
    sort: searchParams.get('sort') || 'newest',
    page: Number(searchParams.get('page') || '1'),
  }
}

// The API parameters for the gig list, from the filters in the URL.
function buildParams(filters, page) {
  const params = { page }
  if (filters.q) params.q = filters.q
  if (filters.category) params.category = filters.category
  if (filters.skillIds.length) params.skills = filters.skillIds.join(',')
  if (filters.budget_min) params.budget_min = filters.budget_min
  if (filters.budget_max) params.budget_max = filters.budget_max
  if (filters.negotiable) params.negotiable = 'true'
  if (filters.includeClosed) params.include_closed = 'true'
  if (filters.county) params.county = filters.county
  if (filters.remote) params.remote = 'true'
  if (filters.urgent) params.urgent = 'true'
  if (filters.deadline_before) params.deadline_before = filters.deadline_before
  if (filters.posted_within) params.posted_within = filters.posted_within
  if (filters.sort) params.sort = filters.sort
  return params
}

// The pills beside "All gigs". Each one is a filter that already exists, so it also shows in the
// chips and in More filters.
function quickFilters(filters) {
  const quickBudget = filters.budget_min === QUICK_BUDGET_MIN && !filters.budget_max
  return [
    { key: 'newest', label: 'Newest', pressed: filters.sort === 'newest', update: { sort: 'newest' } },
    { key: 'urgent', label: 'Urgent', pressed: filters.urgent, update: { urgent: !filters.urgent } },
    { key: 'remote', label: 'Remote', pressed: filters.remote, update: { remote: !filters.remote } },
    { key: 'negotiable', label: 'Negotiable', pressed: filters.negotiable, update: { negotiable: !filters.negotiable } },
    {
      key: 'budget',
      label: 'KES 20,000+',
      pressed: quickBudget,
      update: quickBudget ? { budget_min: '' } : { budget_min: QUICK_BUDGET_MIN, budget_max: '' },
    },
  ]
}

function pillClass(pressed) {
  return `min-h-[40px] px-4 rounded-pill text-[14px] transition-colors ${
    pressed ? 'bg-ink text-white font-semibold' : 'bg-surface text-ink font-medium border border-border hover:bg-sand'
  }`
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
  if (filters.urgent) {
    chips.push({ key: 'urgent', label: 'Urgent', onRemove: () => onChange({ urgent: false }) })
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
  const [filtersOpen, setFiltersOpen] = useState(false)
  // Pages added with "Load more gigs" after the one in the URL.
  const [more, setMore] = useState({ results: [], page: null, loading: false, error: '' })
  const [hero, setHero] = useState({ newToday: 0, newestGig: null })

  const requestIdRef = useRef(0)
  const hasLoadedRef = useRef(false)

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => setCategories([]))
    fetchSkills().then(setSkills).catch(() => setSkills([]))
    Promise.all([fetchGigsPaged({ posted_within: 1, page_size: 1 }), fetchGigsPaged({ page_size: 1 })])
      .then(([today, newest]) => setHero({ newToday: today?.count || 0, newestGig: newest?.results?.[0] || null }))
      .catch(() => {})
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

  // The hero's Search button applies the search straight away instead of waiting for the debounce.
  const submitSearch = () => {
    if (searchInput !== filters.q) updateParams({ q: searchInput }, { resetPage: true })
    document.getElementById('all-gigs-heading')?.scrollIntoView?.({ behavior: 'smooth' })
  }

  useEffect(() => {
    const myRequestId = ++requestIdRef.current
    if (!hasLoadedRef.current) setLoading(true)
    else setFetching(true)
    setError('')
    setMore({ results: [], page: null, loading: false, error: '' })

    fetchGigsPaged(buildParams(filters, filters.page))
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
    filters.urgent,
    filters.deadline_before,
    filters.posted_within,
    filters.sort,
    filters.page,
    retryTick,
  ])

  const lastPage = more.page ?? result?.page ?? 1
  const hasMore = Boolean(result && lastPage < result.total_pages)

  const loadMore = () => {
    const requestId = requestIdRef.current
    setMore((m) => ({ ...m, loading: true, error: '' }))
    fetchGigsPaged(buildParams(filters, lastPage + 1))
      .then((data) => {
        if (requestId !== requestIdRef.current) return
        setMore((m) => ({ results: [...m.results, ...data.results], page: data.page, loading: false, error: '' }))
      })
      .catch(() => {
        if (requestId !== requestIdRef.current) return
        setMore((m) => ({ ...m, loading: false, error: 'Could not load more gigs. Please try again.' }))
      })
  }

  const chips = buildChips(filters, categories, skills, handleFilterChange)
  const gigs = result ? [...result.results, ...more.results] : []
  const firstPosition = result ? (result.page - 1) * result.page_size + 1 : 1
  const topCategory = categories.reduce(
    (best, c) => ((c.open_gig_count || 0) > (best?.open_gig_count || 0) ? c : best),
    null
  )
  const firstName = (user?.full_name || '').trim().split(/\s+/)[0]

  return (
    <div>
      <BrowseHero
        newToday={hero.newToday}
        newestGig={hero.newestGig}
        topCategory={topCategory}
        search={searchInput}
        onSearchChange={setSearchInput}
        onSearchSubmit={submitSearch}
      />

      <CategoryTiles
        categories={categories}
        selected={filters.category}
        onSelect={(slug) => handleFilterChange({ category: slug })}
      />

      {user?.role === 'freelancer' && (
        <RecommendedForYou
          variant="band"
          limit={10}
          heading={firstName ? `Picked for you, ${firstName}` : 'Picked for you'}
          subheading="Based on your skills and the gigs you show interest in."
        />
      )}

      <section
        aria-labelledby="all-gigs-heading"
        className="max-w-page mx-auto px-4 sm:px-8 pt-9 pb-12 flex flex-col gap-[18px]"
      >
        <div className="flex flex-wrap justify-between items-center gap-3">
          <h2 id="all-gigs-heading" className="text-section-heading">
            All gigs
          </h2>
          <div role="group" aria-label="Quick filters" className="flex flex-wrap gap-2">
            {quickFilters(filters).map((pill) => (
              <button
                key={pill.key}
                type="button"
                aria-pressed={pill.pressed}
                onClick={() => updateParams(pill.update, { resetPage: true })}
                className={pillClass(pill.pressed)}
              >
                {pill.label}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setFiltersOpen(true)}
              className={`${pillClass(false)} inline-flex items-center gap-2`}
            >
              <SlidersHorizontal size={16} aria-hidden="true" />
              More filters
            </button>
          </div>
        </div>

        {chips.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {chips.map((chip) => (
              <button
                key={chip.key}
                type="button"
                onClick={chip.onRemove}
                aria-label={`Remove filter: ${chip.label}`}
                className="inline-flex items-center gap-1.5 text-caption font-semibold px-3 py-1.5 rounded-pill bg-primary-light text-primary"
              >
                {chip.label}
                <X size={13} aria-hidden="true" />
              </button>
            ))}
            <button
              type="button"
              onClick={handleClearAll}
              className="text-caption font-semibold text-ink-soft underline px-2"
            >
              Clear all
            </button>
          </div>
        )}

        {error && (
          <Alert type="error">
            {error}{' '}
            <button type="button" onClick={() => setRetryTick((t) => t + 1)} className="font-medium underline">
              Retry
            </button>
          </Alert>
        )}

        {!error && result && (
          <p className="text-caption text-muted">
            {result.count} gig{result.count === 1 ? '' : 's'} found
          </p>
        )}

        {loading && (
          <div className="grid gap-4 grid-cols-[repeat(auto-fill,minmax(min(340px,100%),1fr))]">
            {Array.from({ length: 4 }).map((_, i) => (
              <GigCardSkeleton key={i} />
            ))}
          </div>
        )}

        {!loading && result && result.results.length === 0 && (
          <div className="text-center py-16 border border-dashed border-divider rounded-card">
            <p className="text-section-title text-ink mb-2">No gigs match your filters</p>
            <p className="text-body text-muted mb-4">
              {chips.length > 0
                ? 'Try removing a filter or widening your search.'
                : 'Check back soon. New gigs are posted regularly.'}
            </p>
            {chips.length > 0 && (
              <Button variant="secondary" onClick={handleClearAll}>
                Clear all filters
              </Button>
            )}
          </div>
        )}

        {!loading && gigs.length > 0 && (
          <div
            className={`grid gap-4 grid-cols-[repeat(auto-fill,minmax(min(340px,100%),1fr))] transition-opacity ${
              fetching ? 'opacity-50 pointer-events-none' : ''
            }`}
          >
            {gigs.map((gig, index) => (
              <GigCard key={gig.id} gig={gig} query={filters.q} position={firstPosition + index} />
            ))}
          </div>
        )}

        {more.error && <Alert type="error">{more.error}</Alert>}

        {hasMore && !loading && (
          <button
            type="button"
            onClick={loadMore}
            disabled={more.loading}
            className="self-center inline-flex items-center min-h-[48px] px-[26px] rounded-pill border-2 border-ink text-ink text-[15px] font-bold hover:bg-sand disabled:opacity-50"
          >
            {more.loading ? 'Loading…' : 'Load more gigs'}
          </button>
        )}
      </section>

      {filtersOpen && (
        <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-labelledby="more-filters-heading">
          <div className="absolute inset-0 bg-ink/30" onClick={() => setFiltersOpen(false)} />
          <div className="absolute right-0 top-0 bottom-0 w-[90%] max-w-sm bg-surface p-6 overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 id="more-filters-heading" className="text-section-title text-ink">
                More filters
              </h2>
              <button type="button" onClick={() => setFiltersOpen(false)} aria-label="Close filters">
                <X size={20} className="text-muted" />
              </button>
            </div>
            <label className="block mb-6">
              <span className="block text-label text-ink mb-1.5">Sort by</span>
              <select
                value={filters.sort}
                onChange={(e) => updateParams({ sort: e.target.value }, { resetPage: true })}
                className="w-full h-12 px-3.5 border border-border rounded-input text-body text-ink bg-surface focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              >
                {SORT_OPTIONS.filter((opt) => opt.value !== 'relevance' || filters.q).map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
            <FilterSidebar
              categories={categories}
              counties={counties}
              skills={skills}
              filters={filters}
              onChange={handleFilterChange}
              onClear={handleClearAll}
              heading={false}
            />
            <Button className="w-full mt-6" onClick={() => setFiltersOpen(false)}>
              Show {result ? `${result.count} ` : ''}results
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
