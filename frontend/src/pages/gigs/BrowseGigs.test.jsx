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

    await waitFor(() => expect(fetchGigsPaged).toHaveBeenCalled())

    const params = fetchGigsPaged.mock.calls[0][0]
    expect(params.category).toBe('design-creative')
    expect(params.budget_min).toBe('1000')
    expect(params.negotiable).toBe('true')
    expect(params.sort).toBe('deadline')
  })

  it('pushes the search box into the URL after the debounce delay, resetting the page', async () => {
    renderAt('/gigs?page=3')
    await waitFor(() => expect(fetchGigsPaged).toHaveBeenCalled())

    const input = screen.getByPlaceholderText('Search gigs by title, skill, or description')
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

    const chip = await screen.findByRole('button', { name: /Design & Creative/ })
    fireEvent.click(chip)

    await waitFor(() => {
      expect(screen.getByTestId('location').textContent).toBe('/gigs')
    })
  })

  it('refresh-safe: a direct load with query params round-trips without losing them', async () => {
    renderAt('/gigs?q=design&sort=relevance&deadline_before=2026-12-01')
    await waitFor(() => expect(fetchGigsPaged).toHaveBeenCalled())

    const params = fetchGigsPaged.mock.calls[0][0]
    expect(params.q).toBe('design')
    expect(params.sort).toBe('relevance')
    expect(params.deadline_before).toBe('2026-12-01')
    expect(screen.getByTestId('location').textContent).toBe(
      '/gigs?q=design&sort=relevance&deadline_before=2026-12-01'
    )
  })
})
