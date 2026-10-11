import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import BrowseGigs from './BrowseGigs'
import { fetchCategories, fetchGigsPaged } from '../../api/gigs'
import { fetchSkills } from '../../api/auth'

vi.mock('../../api/gigs', () => ({
  fetchCategories: vi.fn(),
  fetchGigsPaged: vi.fn(),
  logSearchClick: vi.fn(),
}))
vi.mock('../../api/auth', () => ({ fetchSkills: vi.fn(), createSkill: vi.fn() }))
vi.mock('../../api/meta', () => ({
  fetchCounties: vi.fn().mockResolvedValue([
    { value: 'Nairobi', label: 'Nairobi' },
    { value: 'Mombasa', label: 'Mombasa' },
  ]),
}))
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ user: null }) }))

const EMPTY_PAGE = { count: 0, page: 1, page_size: 12, total_pages: 0, next: null, previous: null, results: [] }

function gig(n) {
  return {
    id: `gig-${n}`,
    title: `Gig number ${n}`,
    client_name: 'Amina',
    category: { name: 'Design & Creative' },
    skills: [],
    budget_min: '1000',
    budget_max: '2000',
    currency: 'KES',
    deadline: '2030-01-01',
    application_deadline: '2030-01-01',
    created_at: '2026-01-01T00:00:00Z',
    is_negotiable: false,
    status: 'open',
    county: null,
    is_remote: false,
  }
}

const TWO_GIGS = { ...EMPTY_PAGE, count: 2, total_pages: 1, results: [gig(1), gig(2)] }

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
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

const url = () => screen.getByTestId('location').textContent

beforeEach(() => {
  vi.clearAllMocks()
  fetchCategories.mockResolvedValue([
    { id: 'c1', name: 'Design & Creative', slug: 'design-creative' },
    { id: 'c2', name: 'Local Services', slug: 'local-services' },
  ])
  fetchSkills.mockResolvedValue([{ id: 's1', name: 'Plumbing' }])
  fetchGigsPaged.mockResolvedValue(TWO_GIGS)
})

describe('filters write to the URL', () => {
  it('category', async () => {
    renderAt('/gigs')
    fireEvent.click(await screen.findByRole('radio', { name: 'Local Services' }))
    await waitFor(() => expect(url()).toBe('/gigs?category=local-services'))
  })

  it('county', async () => {
    renderAt('/gigs')
    await screen.findByRole('option', { name: 'Mombasa' })
    fireEvent.change(screen.getByLabelText('County'), { target: { value: 'Mombasa' } })
    await waitFor(() => expect(url()).toBe('/gigs?county=Mombasa'))
  })

  it('remote only', async () => {
    renderAt('/gigs')
    fireEvent.click(await screen.findByLabelText('Remote gigs only'))
    await waitFor(() => expect(url()).toBe('/gigs?remote=true'))
  })

  it('skills', async () => {
    renderAt('/gigs')
    fireEvent.click(await screen.findByRole('button', { name: 'Plumbing' }))
    await waitFor(() => expect(url()).toBe('/gigs?skills=s1'))
  })

  it('budget range', async () => {
    renderAt('/gigs')
    fireEvent.change(await screen.findByLabelText('Minimum budget in KES'), { target: { value: '5000' } })
    await waitFor(() => expect(url()).toBe('/gigs?budget_min=5000'))
    fireEvent.change(screen.getByLabelText('Maximum budget in KES'), { target: { value: '20000' } })
    await waitFor(() => expect(url()).toContain('budget_max=20000'))
  })

  it('posted within', async () => {
    renderAt('/gigs')
    fireEvent.click(await screen.findByRole('radio', { name: 'Last 7 days' }))
    await waitFor(() => expect(url()).toBe('/gigs?posted_within=7'))
  })

  it('deadline before', async () => {
    renderAt('/gigs')
    fireEvent.change(await screen.findByLabelText('Deadline before'), { target: { value: '2026-12-01' } })
    await waitFor(() => expect(url()).toBe('/gigs?deadline_before=2026-12-01'))
  })

  it('negotiable only', async () => {
    renderAt('/gigs')
    fireEvent.click(await screen.findByLabelText('Negotiable budget only'))
    await waitFor(() => expect(url()).toBe('/gigs?negotiable=true'))
  })

  it('sort', async () => {
    renderAt('/gigs')
    fireEvent.change(await screen.findByLabelText('Sort gigs'), { target: { value: 'budget_high' } })
    await waitFor(() => expect(url()).toBe('/gigs?sort=budget_high'))
  })

  it('every change resets to page 1', async () => {
    renderAt('/gigs?page=3')
    fireEvent.click(await screen.findByLabelText('Negotiable budget only'))
    await waitFor(() => expect(url()).toBe('/gigs?negotiable=true'))
  })
})

describe('the closed-gigs toggle', () => {
  it('is off by default and does not send include_closed', async () => {
    renderAt('/gigs')
    expect(await screen.findByLabelText('Show closed gigs')).not.toBeChecked()
    await waitFor(() => expect(fetchGigsPaged).toHaveBeenCalled())
    expect(fetchGigsPaged.mock.calls[0][0]).not.toHaveProperty('include_closed')
  })

  it('writes include_closed to the URL, asks the API for closed gigs, and shows a removable chip', async () => {
    renderAt('/gigs')
    fireEvent.click(await screen.findByLabelText('Show closed gigs'))
    await waitFor(() => expect(url()).toBe('/gigs?include_closed=true'))
    await waitFor(() =>
      expect(fetchGigsPaged).toHaveBeenLastCalledWith(expect.objectContaining({ include_closed: 'true' }))
    )
    fireEvent.click(screen.getByRole('button', { name: 'Remove filter: Including closed gigs' }))
    await waitFor(() => expect(url()).toBe('/gigs'))
  })

  it('is on when the URL already says so', async () => {
    renderAt('/gigs?include_closed=true')
    expect(await screen.findByLabelText('Show closed gigs')).toBeChecked()
  })
})

describe('results states', () => {
  it('shows skeleton cards and announces loading while the first request is pending', async () => {
    fetchGigsPaged.mockReturnValue(new Promise(() => {}))
    const { container } = renderAt('/gigs')
    await waitFor(() => expect(container.querySelectorAll('.animate-pulse')).toHaveLength(6))
    expect(screen.getByRole('status')).toHaveTextContent('Loading gigs')
  })

  it('shows the gigs and announces the count politely', async () => {
    renderAt('/gigs')
    expect(await screen.findByText('Gig number 1')).toBeInTheDocument()
    const status = screen.getByRole('status')
    expect(status).toHaveAttribute('aria-live', 'polite')
    expect(status).toHaveTextContent('2 gigs found')
  })

  it('uses the singular for one gig', async () => {
    fetchGigsPaged.mockResolvedValue({ ...TWO_GIGS, count: 1, results: [gig(1)] })
    renderAt('/gigs')
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('1 gig found'))
  })

  it('explains an empty result with active filters and offers to clear them', async () => {
    fetchGigsPaged.mockResolvedValue(EMPTY_PAGE)
    renderAt('/gigs?category=design-creative')
    expect(await screen.findByText('No gigs match your filters')).toBeInTheDocument()
    expect(screen.getByText('Try removing a filter or widening your search.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Clear all filters' }))
    await waitFor(() => expect(url()).toBe('/gigs'))
  })

  it('has a different empty message, and no clear button, when nothing is filtered', async () => {
    fetchGigsPaged.mockResolvedValue(EMPTY_PAGE)
    renderAt('/gigs')
    expect(await screen.findByText(/Check back soon/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Clear all filters' })).not.toBeInTheDocument()
  })

  it('shows an error with a retry that loads the gigs', async () => {
    fetchGigsPaged.mockRejectedValueOnce({ response: undefined })
    renderAt('/gigs')
    expect(await screen.findByText(/Could not load gigs/)).toBeInTheDocument()
    expect(screen.queryByText('Gig number 1')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))

    expect(await screen.findByText('Gig number 1')).toBeInTheDocument()
    expect(fetchGigsPaged).toHaveBeenCalledTimes(2)
    expect(screen.queryByText(/Could not load gigs/)).not.toBeInTheDocument()
  })

  it('shows the server message for a rejected filter instead of a generic one', async () => {
    fetchGigsPaged.mockRejectedValueOnce({ response: { data: { county: ['Unknown county.'] } } })
    renderAt('/gigs')
    expect(await screen.findByText(/Unknown county\./)).toBeInTheDocument()
  })
})

describe('mobile filter drawer', () => {
  const openDrawer = async () => {
    const trigger = await screen.findByRole('button', { name: 'Filters' })
    fireEvent.click(trigger)
    return trigger
  }

  it('is closed at first and the trigger says so', async () => {
    renderAt('/gigs')
    const trigger = await screen.findByRole('button', { name: 'Filters' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger).toHaveAttribute('aria-haspopup', 'dialog')
  })

  it('opens as a labelled modal dialog and moves focus into it', async () => {
    renderAt('/gigs')
    const trigger = await openDrawer()
    const dialog = screen.getByRole('dialog', { name: 'Filter gigs' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'Close filters' })).toHaveFocus()
  })

  it('closes with Escape and returns focus to the button that opened it', async () => {
    renderAt('/gigs')
    const trigger = await openDrawer()
    fireEvent.keyDown(document.activeElement, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  it('closes with the close button and returns focus', async () => {
    renderAt('/gigs')
    const trigger = await openDrawer()
    fireEvent.click(screen.getByRole('button', { name: 'Close filters' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })

  it('closes with "Show results"', async () => {
    renderAt('/gigs')
    await openDrawer()
    fireEvent.click(screen.getByRole('button', { name: 'Show results' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('keeps Tab inside the dialog, wrapping from the last control to the first', async () => {
    renderAt('/gigs')
    await openDrawer()
    const dialog = screen.getByRole('dialog')
    const focusable = dialog.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])'
    )
    const first = focusable[0]
    const last = focusable[focusable.length - 1]

    last.focus()
    fireEvent.keyDown(last, { key: 'Tab' })
    expect(first).toHaveFocus()
  })

  it('keeps Shift+Tab inside the dialog, wrapping from the first control to the last', async () => {
    renderAt('/gigs')
    await openDrawer()
    const dialog = screen.getByRole('dialog')
    const focusable = dialog.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])'
    )
    const first = focusable[0]
    const last = focusable[focusable.length - 1]

    first.focus()
    fireEvent.keyDown(first, { key: 'Tab', shiftKey: true })
    expect(last).toHaveFocus()
  })

  it('applies a filter chosen inside the drawer to the URL', async () => {
    renderAt('/gigs')
    await openDrawer()
    const dialog = screen.getByRole('dialog')
    fireEvent.click(within(dialog).getByLabelText('Remote gigs only'))
    await waitFor(() => expect(url()).toBe('/gigs?remote=true'))
  })
})

describe('labels for assistive technology', () => {
  it('labels the search box and the sort control', async () => {
    renderAt('/gigs')
    expect(await screen.findByLabelText('Search gigs')).toBeInTheDocument()
    expect(screen.getByLabelText('Sort gigs')).toBeInTheDocument()
  })

  it('gives each filter chip a name that says what removing it does', async () => {
    renderAt('/gigs?remote=true')
    expect(await screen.findByRole('button', { name: 'Remove filter: Remote only' })).toBeInTheDocument()
  })
})
