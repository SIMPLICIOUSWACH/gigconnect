import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import BrowseGigs from './BrowseGigs'
import { fetchCategories, fetchGigsPaged } from '../../api/gigs'
import { fetchSkills } from '../../api/auth'

vi.mock('../../api/gigs', () => ({
  fetchCategories: vi.fn(),
  fetchGigsPaged: vi.fn(),
}))
vi.mock('../../api/meta', () => ({
  fetchCounties: vi.fn().mockResolvedValue([]),
}))
vi.mock('../../api/auth', () => ({
  fetchSkills: vi.fn(),
  createSkill: vi.fn(),
}))
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: null }),
}))

const EMPTY_PAGE = { count: 0, page: 1, page_size: 12, total_pages: 0, next: null, previous: null, results: [] }

// The gig list request: the hero's own requests (today's count, the newest gig) ask for one gig and no page.
const listCalls = () => fetchGigsPaged.mock.calls.map((call) => call[0]).filter((params) => 'page' in params)

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}

function renderAt(initialPath) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path="/gigs"
          element={
            <>
              <BrowseGigs />
              <LocationDisplay />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  )
}

describe('BrowseGigs URL state', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchCategories.mockResolvedValue([{ id: 'cat-1', name: 'Design & Creative', slug: 'design-creative' }])
    fetchSkills.mockResolvedValue([{ id: 'skill-1', name: 'Graphic Design' }])
    fetchGigsPaged.mockResolvedValue(EMPTY_PAGE)
  })

  it('hydrates filters from the URL on load', async () => {
    renderAt('/gigs?category=design-creative&budget_min=1000&negotiable=true&sort=deadline')

    await waitFor(() => expect(listCalls()).toHaveLength(1))

    const params = listCalls()[0]
    expect(params.category).toBe('design-creative')
    expect(params.budget_min).toBe('1000')
    expect(params.negotiable).toBe('true')
    expect(params.sort).toBe('deadline')
  })

  it('pushes the search box into the URL after the debounce delay, resetting the page', async () => {
    renderAt('/gigs?page=3')
    await waitFor(() => expect(fetchGigsPaged).toHaveBeenCalled())

    const input = screen.getByRole('searchbox', { name: 'Search gigs' })
    fireEvent.change(input, { target: { value: 'bakery' } })

    // Before the debounce window elapses, the URL must not have changed yet.
    expect(screen.getByTestId('location').textContent).toBe('/gigs?page=3')

    await waitFor(
      () => {
        const location = screen.getByTestId('location').textContent
        expect(location).toContain('q=bakery')
        expect(location).not.toContain('page=')
      },
      { timeout: 1000 }
    )
  })

  it('removing a filter chip clears it from the URL', async () => {
    renderAt('/gigs?category=design-creative')
    await waitFor(() => expect(fetchGigsPaged).toHaveBeenCalled())

    const chip = await screen.findByRole('button', { name: 'Remove filter: Design & Creative' })
    fireEvent.click(chip)

    await waitFor(() => {
      expect(screen.getByTestId('location').textContent).toBe('/gigs')
    })
  })

  it('refresh-safe: a direct load with query params round-trips without losing them', async () => {
    renderAt('/gigs?q=design&sort=relevance&deadline_before=2026-12-01')
    await waitFor(() => expect(listCalls()).toHaveLength(1))

    const params = listCalls()[0]
    expect(params.q).toBe('design')
    expect(params.sort).toBe('relevance')
    expect(params.deadline_before).toBe('2026-12-01')
    expect(screen.getByTestId('location').textContent).toBe(
      '/gigs?q=design&sort=relevance&deadline_before=2026-12-01'
    )
  })
})

const makeGig = (n) => ({
  id: `g${n}`,
  title: `Gig ${n}`,
  client_id: 'c1',
  client_name: 'Baraka Traders',
  category: { id: 'cat-1', name: 'Design & Creative', slug: 'design-creative' },
  skills: [],
  budget_min: '1000',
  budget_max: '2000',
  currency: 'KES',
  deadline: '2999-01-01',
  application_deadline: '2999-01-01',
  created_at: '2026-10-01T09:00:00Z',
  is_negotiable: false,
  status: 'open',
  county: null,
  is_remote: false,
})

const page = (n, totalPages, results) => ({
  count: totalPages * 2,
  page: n,
  page_size: 2,
  total_pages: totalPages,
  next: n < totalPages ? 'next' : null,
  previous: n > 1 ? 'previous' : null,
  results,
})

describe('BrowseGigs Direction B sections', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchCategories.mockResolvedValue([
      { id: 'cat-1', name: 'Design & Creative', slug: 'design-creative', open_gig_count: 1 },
      { id: 'cat-2', name: 'Writing & Content', slug: 'writing-content', open_gig_count: 4 },
    ])
    fetchSkills.mockResolvedValue([])
    fetchGigsPaged.mockResolvedValue(EMPTY_PAGE)
  })

  it('shows how many gigs were posted today, from the API', async () => {
    fetchGigsPaged.mockImplementation((params) =>
      Promise.resolve(params.posted_within === 1 ? { ...EMPTY_PAGE, count: 36 } : EMPTY_PAGE)
    )
    renderAt('/gigs')
    expect(await screen.findByText('36 new gigs posted today')).toBeInTheDocument()
  })

  it('hides the posted-today badge when nothing was posted today', async () => {
    renderAt('/gigs')
    await waitFor(() => expect(listCalls()).toHaveLength(1))
    expect(screen.queryByText(/posted today/)).not.toBeInTheDocument()
  })

  it('shows each category with its open gig count, and a tile sets the category filter', async () => {
    renderAt('/gigs')
    const tile = await screen.findByRole('button', { name: /Writing & Content\s*4 open gigs/ })
    expect(screen.getByText('1 open gig')).toBeInTheDocument()
    fireEvent.click(tile)
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/gigs?category=writing-content'))
    expect(tile).toHaveAttribute('aria-pressed', 'true')
  })

  it('choosing the selected category tile again clears the filter', async () => {
    renderAt('/gigs?category=writing-content')
    fireEvent.click(await screen.findByRole('button', { name: /Writing & Content\s*4 open gigs/ }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/gigs'))
  })

  it('the Urgent pill filters to urgent gigs and toggles off again', async () => {
    renderAt('/gigs')
    const urgent = await screen.findByRole('button', { name: 'Urgent' })
    fireEvent.click(urgent)
    await waitFor(() => expect(listCalls().at(-1).urgent).toBe('true'))
    expect(screen.getByRole('button', { name: 'Urgent' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'Urgent' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/gigs'))
  })

  it('the KES 20,000+ pill sets a minimum budget of 20,000', async () => {
    renderAt('/gigs')
    fireEvent.click(await screen.findByRole('button', { name: 'KES 20,000+' }))
    await waitFor(() => expect(listCalls().at(-1).budget_min).toBe('20000'))
  })

  it('Load more gigs adds the next page under the first, and disappears on the last page', async () => {
    fetchGigsPaged.mockImplementation((params) => {
      if (!('page' in params)) return Promise.resolve(EMPTY_PAGE)
      return Promise.resolve(params.page === 1 ? page(1, 2, [makeGig(1), makeGig(2)]) : page(2, 2, [makeGig(3)]))
    })
    renderAt('/gigs')
    expect(await screen.findByRole('link', { name: 'Gig 1' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Load more gigs' }))

    expect(await screen.findByRole('link', { name: 'Gig 3' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Gig 1' })).toBeInTheDocument()
    expect(listCalls().at(-1).page).toBe(2)
    expect(screen.queryByRole('button', { name: 'Load more gigs' })).not.toBeInTheDocument()
  })

  it('More filters opens the full filters, including sorting', async () => {
    renderAt('/gigs')
    fireEvent.click(await screen.findByRole('button', { name: 'More filters' }))
    expect(screen.getByRole('dialog', { name: 'More filters' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Sort by' })).toBeInTheDocument()
  })

  it('does not show the Picked for you band to someone who is not a freelancer', async () => {
    renderAt('/gigs')
    await waitFor(() => expect(listCalls()).toHaveLength(1))
    expect(screen.queryByRole('heading', { name: /Picked for you/ })).not.toBeInTheDocument()
  })
})
