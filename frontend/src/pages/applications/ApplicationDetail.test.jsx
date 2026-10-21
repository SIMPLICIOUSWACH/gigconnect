import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ApplicationDetail from './ApplicationDetail'
import { fetchApplication, withdrawApplication } from '../../api/applications'

vi.mock('../../api/applications', () => ({
  fetchApplication: vi.fn(),
  withdrawApplication: vi.fn(),
}))

const makeApplication = (overrides = {}) => ({
  id: 'app-1',
  gig_id: 'gig-1',
  gig_title: 'Logo for a cafe',
  gig_status: 'open',
  client_name: 'Cafe Owner',
  status: 'pending',
  proposed_rate: '1500.00',
  portfolio_link: 'https://example.com/me',
  cover_letter: 'I have five years of experience.',
  created_at: '2026-10-01T09:00:00Z',
  updated_at: '2026-10-01T09:00:00Z',
  allowed_next_statuses: ['withdrawn'],
  events: [{ id: 'e1', from_status: '', to_status: 'pending', changed_by_name: 'Me', note: '', created_at: '2026-10-01T09:00:00Z' }],
  ...overrides,
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/applications/app-1']}>
      <Routes>
        <Route path="/applications/:id" element={<ApplicationDetail />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ApplicationDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows the application, its rate, link and history', async () => {
    fetchApplication.mockResolvedValue(makeApplication())
    renderPage()
    expect(await screen.findByText('Logo for a cafe')).toBeInTheDocument()
    expect(screen.getByText('I have five years of experience.')).toBeInTheDocument()
    expect(screen.getByText('KES 1,500')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'https://example.com/me' })).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.getByText('Pending')).toBeInTheDocument()
    // once in the subtitle, once as the first history entry
    expect(screen.getAllByText(/Applied/)).toHaveLength(2)
  })

  it('says plainly when the application cannot be found', async () => {
    fetchApplication.mockRejectedValue({ response: { status: 404 } })
    renderPage()
    expect(await screen.findByText(/does not exist, or you cannot see it/)).toBeInTheDocument()
  })

  it('offers a retry when loading fails', async () => {
    fetchApplication.mockRejectedValueOnce({ response: { status: 500 } })
    fetchApplication.mockResolvedValueOnce(makeApplication())
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Logo for a cafe')).toBeInTheDocument()
  })

  it('asks for confirmation before withdrawing, and nothing is sent until confirmed', async () => {
    fetchApplication.mockResolvedValue(makeApplication())
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Withdraw application' }))
    expect(screen.getByText(/will not be able to apply to this gig again/)).toBeInTheDocument()
    expect(withdrawApplication).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Keep my application' }))
    expect(screen.getByRole('button', { name: 'Withdraw application' })).toBeInTheDocument()
    expect(withdrawApplication).not.toHaveBeenCalled()
  })

  it('withdraws with the reason and shows the new status', async () => {
    fetchApplication.mockResolvedValue(makeApplication())
    withdrawApplication.mockResolvedValue(makeApplication({ status: 'withdrawn', allowed_next_statuses: [] }))
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Withdraw application' }))
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: 'Found other work' } })
    fireEvent.click(screen.getByRole('button', { name: 'Yes, withdraw' }))
    await waitFor(() => expect(screen.getByText('Withdrawn')).toBeInTheDocument())
    expect(withdrawApplication).toHaveBeenCalledWith('app-1', 'Found other work')
    expect(screen.queryByRole('button', { name: 'Withdraw application' })).not.toBeInTheDocument()
  })

  it('shows the server message if withdrawing fails', async () => {
    fetchApplication.mockResolvedValue(makeApplication())
    withdrawApplication.mockRejectedValue({
      response: { data: { detail: 'An application can only be withdrawn while it is pending or under review.' } },
    })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Withdraw application' }))
    fireEvent.click(screen.getByRole('button', { name: 'Yes, withdraw' }))
    expect(await screen.findByText(/can only be withdrawn while it is pending or under review/)).toBeInTheDocument()
  })

  it('hides Withdraw when the server does not allow it', async () => {
    fetchApplication.mockResolvedValue(makeApplication({ status: 'hired', allowed_next_statuses: [] }))
    renderPage()
    await screen.findByText('Logo for a cafe')
    expect(screen.queryByRole('button', { name: 'Withdraw application' })).not.toBeInTheDocument()
  })
})
