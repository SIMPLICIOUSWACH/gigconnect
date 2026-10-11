import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MyApplications from './MyApplications'
import { fetchMyApplications } from '../../api/applications'

vi.mock('../../api/applications', () => ({ fetchMyApplications: vi.fn() }))

const COUNTS = {
  pending: 2,
  under_review: 1,
  shortlisted: 1,
  hired: 1,
  rejected: 3,
  withdrawn: 0,
  total: 8,
}

const makeRow = (n, overrides = {}) => ({
  id: `app-${n}`,
  gig_id: `gig-${n}`,
  gig_title: `Gig number ${n}`,
  gig_status: 'open',
  client_name: `Client ${n}`,
  status: 'pending',
  proposed_rate: null,
  created_at: '2026-10-01T09:00:00Z',
  updated_at: '2026-10-01T09:00:00Z',
  ...overrides,
})

const makePage = (rows, overrides = {}) => ({
  count: rows.length,
  page: 1,
  page_size: 12,
  total_pages: 1,
  next: null,
  previous: null,
  results: rows,
  status_counts: COUNTS,
  ...overrides,
})

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}

function renderAt(path = '/applications') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/applications"
          element={
            <>
              <MyApplications />
              <LocationDisplay />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  )
}

describe('MyApplications', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows the status boxes with the numbers from the server', async () => {
    fetchMyApplications.mockResolvedValue(makePage([makeRow(1)]))
    renderAt()
    await screen.findByText('Gig number 1')
    const boxes = screen.getAllByRole('term').map((term) => [term.textContent, term.nextSibling.textContent])
    expect(boxes).toEqual([
      ['Total', '8'],
      ['Pending', '2'],
      ['Shortlisted', '1'],
      ['Hired', '1'],
      ['Not selected', '3'],
    ])
  })

  it('shows each row with the gig, client, date and status, linked to the gig and the application', async () => {
    fetchMyApplications.mockResolvedValue(makePage([makeRow(1, { status: 'shortlisted' })]))
    renderAt()
    const link = await screen.findByRole('link', { name: 'Gig number 1' })
    expect(link).toHaveAttribute('href', '/gigs/gig-1')
    expect(screen.getByText(/Client 1/)).toBeInTheDocument()
    expect(screen.getByText(/Oct 1, 2026/)).toBeInTheDocument()
    expect(screen.getByText('Shortlisted', { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View application' })).toHaveAttribute('href', '/applications/app-1')
  })

  it('shows a count on every tab', async () => {
    fetchMyApplications.mockResolvedValue(makePage([makeRow(1)]))
    renderAt()
    await screen.findByText('Gig number 1')
    const nav = screen.getByRole('navigation', { name: 'Filter applications by status' })
    expect(within(nav).getByRole('button', { name: 'All (8)' })).toBeInTheDocument()
    expect(within(nav).getByRole('button', { name: 'Under review (1)' })).toBeInTheDocument()
    expect(within(nav).getByRole('button', { name: 'Withdrawn (0)' })).toBeInTheDocument()
  })

  it('reads the selected tab from the URL and asks the server for it', async () => {
    fetchMyApplications.mockResolvedValue(makePage([makeRow(1)]))
    renderAt('/applications?status=hired')
    await screen.findByText('Gig number 1')
    expect(fetchMyApplications).toHaveBeenCalledWith({ page: 1, status: 'hired' })
    expect(screen.getByRole('button', { name: /^Hired/ })).toHaveAttribute('aria-current', 'true')
  })

  it('writes the selected tab to the URL when a tab is clicked', async () => {
    fetchMyApplications.mockResolvedValue(makePage([makeRow(1)]))
    renderAt()
    await screen.findByText('Gig number 1')
    fireEvent.click(screen.getByRole('button', { name: /^Shortlisted/ }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/applications?status=shortlisted'))
    await waitFor(() => expect(fetchMyApplications).toHaveBeenLastCalledWith({ page: 1, status: 'shortlisted' }))
  })

  it('ignores an unknown status in the URL', async () => {
    fetchMyApplications.mockResolvedValue(makePage([makeRow(1)]))
    renderAt('/applications?status=nonsense')
    await screen.findByText('Gig number 1')
    expect(fetchMyApplications).toHaveBeenCalledWith({ page: 1 })
    expect(screen.getByRole('button', { name: /^All/ })).toHaveAttribute('aria-current', 'true')
  })

  it('shows skeletons while the first load is in flight', () => {
    fetchMyApplications.mockReturnValue(new Promise(() => {}))
    renderAt()
    expect(screen.getByLabelText('Loading applications')).toBeInTheDocument()
  })

  it('tells a freelancer with no applications how to start, without showing numbers', async () => {
    fetchMyApplications.mockResolvedValue(
      makePage([], { status_counts: { ...COUNTS, pending: 0, under_review: 0, shortlisted: 0, hired: 0, rejected: 0, total: 0 } })
    )
    renderAt()
    expect(await screen.findByText("You haven't applied to any gigs yet")).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Browse gigs' })).toHaveAttribute('href', '/gigs')
  })

  it('has a different empty state for a tab with nothing in it', async () => {
    fetchMyApplications.mockResolvedValue(makePage([]))
    renderAt('/applications?status=withdrawn')
    expect(await screen.findByText('No withdrawn applications')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Show all applications' }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/applications'))
  })

  it('shows an error with a Retry that loads again', async () => {
    fetchMyApplications.mockRejectedValueOnce({ response: { status: 500 } })
    fetchMyApplications.mockResolvedValueOnce(makePage([makeRow(1)]))
    renderAt()
    expect(await screen.findByText(/Could not load your applications/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Gig number 1')).toBeInTheDocument()
    expect(screen.queryByText(/Could not load your applications/)).not.toBeInTheDocument()
  })

  it('pages through results and keeps the page in the URL', async () => {
    fetchMyApplications.mockResolvedValue(makePage([makeRow(1)], { total_pages: 2, next: 'x' }))
    renderAt()
    await screen.findByText('Page 1 of 2')
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/applications?page=2'))
    await waitFor(() => expect(fetchMyApplications).toHaveBeenLastCalledWith({ page: 2 }))
  })

  it('goes back to page 1 when the page in the URL no longer exists', async () => {
    fetchMyApplications.mockRejectedValueOnce({ response: { status: 404 } })
    fetchMyApplications.mockResolvedValueOnce(makePage([makeRow(1)]))
    renderAt('/applications?page=9')
    expect(await screen.findByText('Gig number 1')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/applications$/)
  })
})
