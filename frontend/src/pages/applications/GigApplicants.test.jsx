import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GigApplicants from './GigApplicants'
import { fetchGigApplicants, updateApplicationStatus } from '../../api/applications'
import { fetchGig } from '../../api/gigs'

vi.mock('../../api/applications', () => ({
  fetchGigApplicants: vi.fn(),
  updateApplicationStatus: vi.fn(),
}))
vi.mock('../../api/gigs', () => ({ fetchGig: vi.fn() }))

const COUNTS = { pending: 1, under_review: 0, shortlisted: 1, hired: 0, rejected: 0, withdrawn: 0, total: 2 }

const makeApplicant = (n, overrides = {}) => ({
  id: `app-${n}`,
  gig_id: 'gig-1',
  gig_title: 'Logo for a cafe',
  gig_status: 'open',
  client_name: 'Cafe Owner',
  status: 'pending',
  proposed_rate: '1500.00',
  created_at: '2026-10-01T09:00:00Z',
  updated_at: '2026-10-01T09:00:00Z',
  cover_letter: `Cover letter from applicant ${n}.`,
  portfolio_link: `https://example.com/${n}`,
  applicant: {
    id: `user-${n}`,
    full_name: `Applicant ${n}`,
    verification_status: 'unverified',
    verified: false,
    skills: [{ id: `s${n}`, name: `Skill ${n}` }],
  },
  events: [
    { id: `e${n}`, from_status: '', to_status: 'pending', changed_by_name: `Applicant ${n}`, note: '', created_at: '2026-10-01T09:00:00Z' },
  ],
  allowed_next_statuses: ['under_review', 'rejected'],
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

function renderAt(path = '/gigs/gig-1/applicants') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/gigs/:id/applicants"
          element={
            <>
              <GigApplicants />
              <LocationDisplay />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  )
}

describe('GigApplicants page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchGig.mockResolvedValue({ id: 'gig-1', title: 'Logo for a cafe', status: 'open' })
  })

  it('shows each applicant with name, skills, cover letter, portfolio link and rate', async () => {
    fetchGigApplicants.mockResolvedValue(makePage([makeApplicant(1)]))
    renderAt()
    expect(await screen.findByRole('link', { name: 'Applicant 1' })).toHaveAttribute('href', '/profile/user-1')
    expect(screen.getByText('Skill 1')).toBeInTheDocument()
    expect(screen.getByText('Cover letter from applicant 1.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'https://example.com/1' })).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.getByText(/Proposes KES 1,500/)).toBeInTheDocument()
    expect(await screen.findByText(/Logo for a cafe/)).toBeInTheDocument()
  })

  it('shows the Verified badge only for an applicant who is actually verified', async () => {
    const verified = makeApplicant(1, { applicant: { ...makeApplicant(1).applicant, verified: true } })
    fetchGigApplicants.mockResolvedValue(makePage([verified, makeApplicant(2)]))
    renderAt()
    await screen.findByText('Applicant 2')
    expect(screen.getAllByText('Verified')).toHaveLength(1)
  })

  it('leaves a clearly marked spot for the match score and shows no score', async () => {
    fetchGigApplicants.mockResolvedValue(makePage([makeApplicant(1)]))
    renderAt()
    expect(await screen.findByText(/Match scores arrive with the recommendation engine/)).toBeInTheDocument()
    expect(screen.queryByText(/\d+\s*%/)).not.toBeInTheDocument()
  })

  it('offers exactly the moves the server allows', async () => {
    fetchGigApplicants.mockResolvedValue(
      makePage([makeApplicant(1, { status: 'shortlisted', allowed_next_statuses: ['hired', 'rejected'] }), makeApplicant(2, { status: 'hired', allowed_next_statuses: [] })])
    )
    renderAt()
    await screen.findByText('Applicant 2')
    expect(screen.getByRole('button', { name: 'Hire' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reject' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Start review' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^(Start review|Shortlist|Hire|Reject)$/ })).toHaveLength(2)
  })

  it('moves an application to review straight away and loads the list again', async () => {
    fetchGigApplicants.mockResolvedValue(makePage([makeApplicant(1)]))
    updateApplicationStatus.mockResolvedValue({})
    renderAt()
    fireEvent.click(await screen.findByRole('button', { name: 'Start review' }))
    await waitFor(() => expect(updateApplicationStatus).toHaveBeenCalledWith('app-1', 'under_review', undefined))
    await waitFor(() => expect(fetchGigApplicants).toHaveBeenCalledTimes(2))
  })

  it('asks for confirmation before rejecting, with an optional note', async () => {
    fetchGigApplicants.mockResolvedValue(makePage([makeApplicant(1)]))
    updateApplicationStatus.mockResolvedValue({})
    renderAt()
    fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))
    expect(updateApplicationStatus).not.toHaveBeenCalled()
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: '  Budget too high  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Yes, reject' }))
    await waitFor(() => expect(updateApplicationStatus).toHaveBeenCalledWith('app-1', 'rejected', 'Budget too high'))
  })

  it('explains what hiring does before confirming it', async () => {
    fetchGigApplicants.mockResolvedValue(
      makePage([makeApplicant(1, { status: 'shortlisted', allowed_next_statuses: ['hired', 'rejected'] })])
    )
    renderAt()
    fireEvent.click(await screen.findByRole('button', { name: 'Hire' }))
    expect(screen.getByText(/moves this gig to In progress. Other applicants are not changed/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(updateApplicationStatus).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Hire' })).toBeInTheDocument()
  })

  it('shows the server message when a move is refused', async () => {
    fetchGigApplicants.mockResolvedValue(
      makePage([makeApplicant(1, { status: 'shortlisted', allowed_next_statuses: ['hired'] })])
    )
    updateApplicationStatus.mockRejectedValue({ response: { data: { detail: 'You have already hired someone for this gig.' } } })
    renderAt()
    fireEvent.click(await screen.findByRole('button', { name: 'Hire' }))
    fireEvent.click(screen.getByRole('button', { name: 'Yes, hire' }))
    expect(await screen.findByText('You have already hired someone for this gig.')).toBeInTheDocument()
  })

  it('shows the status history of each applicant', async () => {
    fetchGigApplicants.mockResolvedValue(makePage([makeApplicant(1)]))
    renderAt()
    const summary = await screen.findByText('Status history (1)')
    expect(within(summary.closest('details')).getByText(/Applicant 1/)).toBeInTheDocument()
  })

  it('filters by status through the URL', async () => {
    fetchGigApplicants.mockResolvedValue(makePage([makeApplicant(1)]))
    renderAt('/gigs/gig-1/applicants?status=shortlisted')
    await screen.findByText('Applicant 1')
    expect(fetchGigApplicants).toHaveBeenCalledWith('gig-1', { page: 1, status: 'shortlisted' })
    fireEvent.click(screen.getByRole('button', { name: /^Pending/ }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/gigs/gig-1/applicants?status=pending'))
  })

  it('shows an empty state when nobody has applied', async () => {
    fetchGigApplicants.mockResolvedValue(makePage([], { status_counts: { ...COUNTS, pending: 0, shortlisted: 0, total: 0 } }))
    renderAt()
    expect(await screen.findByText('No one has applied yet')).toBeInTheDocument()
  })

  it('shows an error with Retry', async () => {
    fetchGigApplicants.mockRejectedValueOnce({ response: { status: 500 } })
    fetchGigApplicants.mockResolvedValueOnce(makePage([makeApplicant(1)]))
    renderAt()
    expect(await screen.findByText(/Could not load the applicants/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Applicant 1')).toBeInTheDocument()
  })

  it('tells someone else\'s client they cannot see these applicants', async () => {
    fetchGigApplicants.mockRejectedValue({ response: { status: 403 } })
    renderAt()
    expect(await screen.findByText('You can only see applicants for your own gigs.')).toBeInTheDocument()
  })
})
