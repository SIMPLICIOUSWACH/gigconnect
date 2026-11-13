import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchSkills } from '../../api/auth'
import {
  fetchInvitableGigs,
  fetchSuggestedFreelancers,
  inviteToApply,
  searchFreelancers,
} from '../../api/freelancers'
import SuggestedFreelancers from '../../components/freelancers/SuggestedFreelancers'
import FindFreelancers from './FindFreelancers'

let mockUser = { id: 'c1', role: 'client' }
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))
vi.mock('../../api/auth', async (importOriginal) => ({ ...(await importOriginal()), fetchSkills: vi.fn() }))
vi.mock('../../api/meta', () => ({
  fetchCounties: vi.fn(() => Promise.resolve([{ value: 'Nairobi', label: 'Nairobi' }])),
}))
vi.mock('../../api/freelancers', async (importOriginal) => ({
  ...(await importOriginal()),
  searchFreelancers: vi.fn(),
  fetchSuggestedFreelancers: vi.fn(),
  fetchInvitableGigs: vi.fn(),
  inviteToApply: vi.fn(),
}))

const AMINA = {
  id: 'f1',
  full_name: 'Amina Wanjiru',
  profile_photo: null,
  profile_colour: 'teal',
  verified: true,
  headline: 'Brand and logo designer',
  county: 'Nairobi',
  skills: [{ id: 's1', name: 'Logo Design' }],
  skills_total: 3,
  rating_avg: '4.60',
  rating_count: 12,
  gigs_completed: 9,
  starting_price: 5000,
  is_available: true,
  open_to_remote: true,
}
const NEWCOMER = { ...AMINA, id: 'f2', full_name: 'David Kamau', verified: false, rating_avg: null, rating_count: 0, gigs_completed: 0 }

const page = (results, extra = {}) => ({ count: results.length, page: 1, total_pages: 1, results, ...extra })

function Where() {
  return <p data-testid="search">{useLocation().search}</p>
}

function renderPage(path = '/freelancers') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/freelancers"
          element={
            <>
              <FindFreelancers />
              <Where />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  )
}

describe('Find freelancers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUser = { id: 'c1', role: 'client' }
    fetchSkills.mockResolvedValue([{ id: 's1', name: 'Logo Design' }])
    searchFreelancers.mockResolvedValue(page([AMINA, NEWCOMER]))
  })

  it('shows a card with the rating, or New for someone with no reviews', async () => {
    renderPage()
    const amina = (await screen.findByRole('heading', { name: /Amina Wanjiru/ })).closest('article')
    expect(within(amina).getByText('4.6')).toBeInTheDocument()
    expect(within(amina).getByText('· 12 reviews')).toBeInTheDocument()
    expect(within(amina).getByRole('img', { name: 'Verified freelancer' })).toBeInTheDocument()
    expect(within(amina).getByText('9 gigs completed')).toBeInTheDocument()
    expect(within(amina).getByText('From KES 5,000')).toBeInTheDocument()
    expect(within(amina).getByText('Available now')).toBeInTheDocument()
    expect(within(amina).getByText('+2 more')).toBeInTheDocument()
    expect(within(amina).getByRole('link', { name: /View profile/ })).toHaveAttribute('href', '/profile/f1')

    const newcomer = screen.getByRole('heading', { name: /David Kamau/ }).closest('article')
    expect(within(newcomer).getByText('New')).toBeInTheDocument()
    expect(within(newcomer).queryByRole('img', { name: 'Verified freelancer' })).not.toBeInTheDocument()
  })

  it('reads the filters from the URL and sends them to the API', async () => {
    renderPage('/freelancers?q=logo&skills=s1&county=Nairobi&verified=true&min_rating=4&sort=rating')
    await screen.findByRole('heading', { name: /Amina Wanjiru/ })
    expect(searchFreelancers).toHaveBeenCalledWith({
      page: 1,
      q: 'logo',
      skills: 's1',
      county: 'Nairobi',
      verified: 'true',
      min_rating: '4',
      sort: 'rating',
    })
    expect(screen.getByRole('button', { name: 'Verified ID only' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Remove filter: Logo Design' })).toBeInTheDocument()
  })

  it('puts a search and a filter into the URL', async () => {
    renderPage()
    await screen.findByRole('heading', { name: /Amina Wanjiru/ })
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search freelancers' }), { target: { value: 'plumber' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    fireEvent.click(screen.getByRole('button', { name: 'Available now' }))
    await waitFor(() => expect(screen.getByTestId('search')).toHaveTextContent('?q=plumber&available=true'))
    expect(searchFreelancers).toHaveBeenLastCalledWith({ page: 1, q: 'plumber', available: 'true' })
  })

  it('loads more, 12 at a time', async () => {
    searchFreelancers.mockResolvedValueOnce(page([AMINA], { count: 13, total_pages: 2 }))
    renderPage()
    await screen.findByRole('heading', { name: /Amina Wanjiru/ })
    searchFreelancers.mockResolvedValueOnce(page([NEWCOMER], { count: 13, page: 2, total_pages: 2 }))
    fireEvent.click(screen.getByRole('button', { name: 'Load more freelancers' }))
    expect(await screen.findByRole('heading', { name: /David Kamau/ })).toBeInTheDocument()
    expect(searchFreelancers).toHaveBeenLastCalledWith({ page: 2 })
    expect(screen.queryByRole('button', { name: 'Load more freelancers' })).not.toBeInTheDocument()
  })

  it('invites a freelancer to one of my open gigs', async () => {
    fetchInvitableGigs.mockResolvedValue({
      invites_left: 20,
      gigs: [
        { id: 'g1', title: 'Menu design', invited: true, applied: false },
        { id: 'g2', title: 'Logo for a bakery', invited: false, applied: false },
      ],
    })
    inviteToApply.mockResolvedValue({ detail: 'Amina Wanjiru was invited to apply.' })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Invite to apply Amina Wanjiru' }))
    const dialog = await screen.findByRole('dialog', { name: 'Invite Amina Wanjiru to apply' })
    expect(await within(dialog).findByRole('radio', { name: /Menu design/ })).toBeDisabled()
    expect(within(dialog).getByRole('radio', { name: /Logo for a bakery/ })).toBeChecked()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Send invitation' }))
    await waitFor(() => expect(inviteToApply).toHaveBeenCalledWith('g2', 'f1'))
    expect(await screen.findByText('Amina Wanjiru was invited to apply.')).toBeInTheDocument()
  })

  it('has no invite button for an admin, who has no gigs', async () => {
    mockUser = { id: 'a1', role: 'admin' }
    renderPage()
    await screen.findByRole('heading', { name: /Amina Wanjiru/ })
    expect(screen.queryByRole('button', { name: /Invite to apply/ })).not.toBeInTheDocument()
  })

  it('has an empty state', async () => {
    searchFreelancers.mockResolvedValue(page([]))
    renderPage('/freelancers?q=zzz')
    expect(await screen.findByText('No freelancers match')).toBeInTheDocument()
  })
})

describe('Suggested for this gig', () => {
  const suggestion = {
    ...AMINA,
    match_score: 0.42,
    match_band: 'strong',
    match_reasons: ['Logo Design', 'Branding'],
    invited: false,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    fetchSuggestedFreelancers.mockResolvedValue({
      results: [suggestion],
      suggestions: { available: true, reason: null },
    })
  })

  it('shows the same match label and shared skills as applicant cards, and invites directly', async () => {
    inviteToApply.mockResolvedValue({ detail: 'Amina Wanjiru was invited to apply.' })
    render(
      <MemoryRouter>
        <SuggestedFreelancers gigId="g1" />
      </MemoryRouter>
    )
    expect(await screen.findByText('Strong skill overlap')).toBeInTheDocument()
    expect(screen.getByText(/Shared skills: Logo Design, Branding/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Invite to apply Amina Wanjiru' }))
    await waitFor(() => expect(inviteToApply).toHaveBeenCalledWith('g1', 'f1'))
    expect(await screen.findByText('Invited')).toBeInTheDocument()
  })

  it('in My gigs it only asks the server once opened', async () => {
    render(
      <MemoryRouter>
        <SuggestedFreelancers gigId="g1" collapsed />
      </MemoryRouter>
    )
    expect(fetchSuggestedFreelancers).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /Suggested freelancers for this gig/ }))
    expect(await screen.findByRole('heading', { name: /Amina Wanjiru/ })).toBeInTheDocument()
    expect(fetchSuggestedFreelancers).toHaveBeenCalledWith('g1')
  })

  it('says so when there is no model to suggest with', async () => {
    fetchSuggestedFreelancers.mockResolvedValue({ results: [], suggestions: { available: false, reason: 'disabled' } })
    render(
      <MemoryRouter>
        <SuggestedFreelancers gigId="g1" />
      </MemoryRouter>
    )
    expect(await screen.findByText('Suggestions are not available right now.')).toBeInTheDocument()
  })
})
