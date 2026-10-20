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
  match_score: null,
  match_band: null,
  match_reasons: [],
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

  describe('skill match', () => {
    const strong = { match_score: 0.62, match_band: 'strong', match_reasons: ['Django', 'PostgreSQL'] }

    it('shows the band and the shared skills when the model scored this applicant', async () => {
      fetchGigApplicants.mockResolvedValue(makePage([makeApplicant(1, strong)]))
      renderAt()
      expect(await screen.findByText('Strong skill overlap')).toBeInTheDocument()
      expect(screen.getByText('Shared skills: Django, PostgreSQL')).toBeInTheDocument()
    })

    it.each([
      ['strong', 'Strong skill overlap'],
      ['good', 'Good skill overlap'],
      ['some', 'Some skill overlap'],
    ])('describes the %s band in words', async (band, label) => {
      fetchGigApplicants.mockResolvedValue(
        makePage([makeApplicant(1, { match_score: 0.2, match_band: band, match_reasons: ['Django'] })])
      )
      renderAt()
      expect(await screen.findByText(label)).toBeInTheDocument()
    })

    it('never shows the number behind the band, or a percentage', async () => {
      fetchGigApplicants.mockResolvedValue(makePage([makeApplicant(1, strong)]))
      renderAt()
      await screen.findByText('Strong skill overlap')
      expect(screen.queryByText(/0\.62|62/)).not.toBeInTheDocument()
      expect(screen.queryByText(/%/)).not.toBeInTheDocument()
    })

    it('says plainly when there is no score, and does not turn that into a low one', async () => {
      fetchGigApplicants.mockResolvedValue(
        makePage([makeApplicant(1, { match_score: null, match_band: null, match_reasons: [] })])
      )
      renderAt()
      expect(await screen.findByText('Match score not available')).toBeInTheDocument()
      expect(screen.queryByText(/skill overlap/)).not.toBeInTheDocument()
      expect(screen.queryByText(/No shared skills/)).not.toBeInTheDocument()
    })

    it('says so when the model scored the applicant and found no shared skill', async () => {
      fetchGigApplicants.mockResolvedValue(
        makePage([makeApplicant(1, { match_score: 0, match_band: null, match_reasons: [] })])
      )
      renderAt()
      expect(await screen.findByText('No shared skills with this gig')).toBeInTheDocument()
      expect(screen.queryByText(/skill overlap/)).not.toBeInTheDocument()
    })

    it('does not show a shared-skills line when the band is missing', async () => {
      fetchGigApplicants.mockResolvedValue(
        makePage([makeApplicant(1, { match_score: null, match_band: null, match_reasons: ['Django'] })])
      )
      renderAt()
      await screen.findByText('Match score not available')
      expect(screen.queryByText(/Shared skills/)).not.toBeInTheDocument()
    })

    it('has no leftover promise that scores arrive later', async () => {
      fetchGigApplicants.mockResolvedValue(makePage([makeApplicant(1)]))
      renderAt()
      await screen.findByText('Applicant 1')
      expect(screen.queryByText(/arrive with the recommendation engine/)).not.toBeInTheDocument()
    })

    it('uses the same plain styling for every band', async () => {
      fetchGigApplicants.mockResolvedValue(
        makePage([
          makeApplicant(1, { match_score: 0.6, match_band: 'strong', match_reasons: ['A'] }),
          makeApplicant(2, { match_score: 0.05, match_band: 'some', match_reasons: ['A'] }),
        ])
      )
      renderAt()
      const strongBox = (await screen.findByText('Strong skill overlap')).closest('div')
      const someBox = screen.getByText('Some skill overlap').closest('div')
      expect(strongBox.className).toBe(someBox.className)
      expect(strongBox.className).not.toMatch(/green|red|amber|accent/)
    })
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
