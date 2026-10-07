import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GigDetail from './GigDetail'
import { fetchGig } from '../../api/gigs'
import { applyToGig } from '../../api/applications'

vi.mock('../../api/gigs', () => ({ fetchGig: vi.fn() }))
vi.mock('../../api/applications', () => ({ applyToGig: vi.fn() }))

let mockUser = null
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

const LETTER = 'I have five years of experience building exactly this kind of thing for small businesses.'
const FUTURE = '2999-01-01'

const makeGig = (overrides = {}) => ({
  id: 'gig-1',
  title: 'Logo for a cafe',
  description: 'Design a logo.',
  client: { id: 'c1', full_name: 'Client', company_name: '' },
  category: { name: 'Design' },
  budget_min: '1000',
  budget_max: '2000',
  currency: 'KES',
  deadline: FUTURE,
  application_deadline: FUTURE,
  is_negotiable: false,
  county: null,
  is_remote: false,
  status: 'open',
  skills: [],
  view_count: 3,
  my_application: null,
  ...overrides,
})

const freelancer = { id: 'f1', role: 'freelancer', is_email_verified: true }

function renderGig(gig, user) {
  mockUser = user
  fetchGig.mockResolvedValue(gig)
  return render(
    <MemoryRouter initialEntries={['/gigs/gig-1']}>
      <Routes>
        <Route path="/gigs/:id" element={<GigDetail />} />
      </Routes>
    </MemoryRouter>
  )
}

const waitForGig = () => screen.findByText('Logo for a cafe')

describe('GigDetail apply button', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows Apply to a verified freelancer on an open gig', async () => {
    renderGig(makeGig(), freelancer)
    await waitForGig()
    expect(screen.getByRole('button', { name: 'Apply' })).toBeInTheDocument()
  })

  it('shows nothing to apply with for a client', async () => {
    renderGig(makeGig(), { id: 'c1', role: 'client', is_email_verified: true })
    await waitForGig()
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument()
  })

  it('shows nothing to apply with when signed out', async () => {
    renderGig(makeGig(), null)
    await waitForGig()
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument()
  })

  it('says applications are closed once the deadline has passed', async () => {
    renderGig(makeGig({ application_deadline: '2000-01-01' }), freelancer)
    await waitForGig()
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument()
    expect(screen.getByText(/Applications closed on/)).toBeInTheDocument()
  })

  it.each(['in_progress', 'completed', 'closed'])('does not offer Apply on a %s gig', async (status) => {
    renderGig(makeGig({ status }), freelancer)
    await waitForGig()
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument()
    expect(screen.getByText('This gig is no longer accepting applications.')).toBeInTheDocument()
  })

  it('asks an unverified freelancer to verify their email instead of offering Apply', async () => {
    renderGig(makeGig(), { ...freelancer, is_email_verified: false })
    await waitForGig()
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument()
    expect(screen.getByText(/Verify your email/)).toBeInTheDocument()
  })

  it('shows Applied, the status and a link once the freelancer has applied', async () => {
    renderGig(makeGig({ my_application: { id: 'app-1', status: 'shortlisted' } }), freelancer)
    await waitForGig()
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument()
    expect(screen.getByText('Applied')).toBeInTheDocument()
    expect(screen.getByText('Shortlisted')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View your application' })).toHaveAttribute('href', '/applications/app-1')
  })

  it('says so when the freelancer withdrew', async () => {
    renderGig(makeGig({ my_application: { id: 'app-1', status: 'withdrawn' } }), freelancer)
    await waitForGig()
    expect(screen.getByText('You withdrew your application')).toBeInTheDocument()
  })
})

describe('GigDetail apply form', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  async function openForm() {
    renderGig(makeGig(), freelancer)
    await waitForGig()
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
    return screen.findByLabelText(/Cover letter/)
  }

  it('opens the form and counts characters', async () => {
    const letter = await openForm()
    fireEvent.change(letter, { target: { value: 'Hello there' } })
    expect(screen.getByText(/11 \/ 3000/)).toBeInTheDocument()
  })

  it('shows inline errors and sends nothing when the letter is too short', async () => {
    const letter = await openForm()
    fireEvent.change(letter, { target: { value: 'Too short' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send application' }))
    expect(await screen.findByText(/at least 50 characters/)).toBeInTheDocument()
    expect(applyToGig).not.toHaveBeenCalled()
  })

  it('sends the application and then shows Applied with its status', async () => {
    applyToGig.mockResolvedValue({ id: 'app-9', status: 'pending' })
    const letter = await openForm()
    fireEvent.change(letter, { target: { value: LETTER } })
    fireEvent.click(screen.getByRole('button', { name: 'Send application' }))
    await waitFor(() => expect(screen.getByText('Applied')).toBeInTheDocument())
    expect(applyToGig).toHaveBeenCalledWith('gig-1', { cover_letter: LETTER })
    expect(screen.getByText('Pending')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View your application' })).toHaveAttribute('href', '/applications/app-9')
  })

  it('shows a server rule error in plain language and keeps the form open', async () => {
    applyToGig.mockRejectedValue({ response: { data: { detail: 'You have already applied to this gig.' } } })
    const letter = await openForm()
    fireEvent.change(letter, { target: { value: LETTER } })
    fireEvent.click(screen.getByRole('button', { name: 'Send application' }))
    expect(await screen.findByText('You have already applied to this gig.')).toBeInTheDocument()
    expect(screen.getByLabelText(/Cover letter/)).toHaveValue(LETTER)
  })

  it('cancel closes the form without sending', async () => {
    await openForm()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'Apply' })).toBeInTheDocument()
    expect(applyToGig).not.toHaveBeenCalled()
  })
})
