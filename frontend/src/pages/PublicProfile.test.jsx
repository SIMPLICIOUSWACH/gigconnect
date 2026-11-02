import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchGigsPaged, logSearchClick } from '../api/gigs'
import { fetchPublicProfile } from '../api/profile'
import PublicProfile from './PublicProfile'

vi.mock('../api/profile', () => ({ fetchPublicProfile: vi.fn() }))
vi.mock('../api/gigs', () => ({ fetchGigsPaged: vi.fn(), logSearchClick: vi.fn() }))
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ user: { id: 'someone-else', role: 'freelancer' } }) }))

const CLIENT = {
  id: 'c1',
  role: 'client',
  full_name: 'Kevin Chege',
  profile: { company_name: 'Zawadi Ltd', industry: 'finance', company_logo: null },
}

const GIG = {
  id: 'g1',
  title: 'Monthly bookkeeping',
  client_id: 'c1',
  client_name: 'Kevin Chege',
  category: { id: 'cat', name: 'Data & Analytics', slug: 'data-analytics' },
  budget_min: '5000.00',
  budget_max: '10000.00',
  currency: 'KES',
  deadline: '2026-12-30',
  application_deadline: '2026-12-20',
  is_negotiable: true,
  county: 'Nairobi',
  is_remote: false,
  status: 'open',
  skills: [{ id: 's1', name: 'Bookkeeping' }],
  created_at: '2026-10-20T10:00:00Z',
}

function renderProfile() {
  return render(
    <MemoryRouter initialEntries={['/profile/c1']}>
      <Routes>
        <Route path="/profile/:id" element={<PublicProfile />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('PublicProfile for a client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchPublicProfile.mockResolvedValue(CLIENT)
  })

  it("lists the client's open gigs", async () => {
    fetchGigsPaged.mockResolvedValue({ count: 1, results: [GIG] })
    renderProfile()
    expect(await screen.findByRole('link', { name: 'Monthly bookkeeping' })).toHaveAttribute('href', '/gigs/g1')
    expect(fetchGigsPaged).toHaveBeenCalledWith({ client: 'c1', page_size: 12 })
    expect(screen.getByRole('heading', { name: 'Open gigs' })).toBeInTheDocument()
  })

  it('says so when there are more gigs than it shows', async () => {
    fetchGigsPaged.mockResolvedValue({ count: 20, results: [GIG] })
    renderProfile()
    expect(await screen.findByText('Showing the newest 1 of 20')).toBeInTheDocument()
  })

  it('has a plain message when nothing is open', async () => {
    fetchGigsPaged.mockResolvedValue({ count: 0, results: [] })
    renderProfile()
    expect(await screen.findByText('Zawadi Ltd has no gigs open for applications right now.')).toBeInTheDocument()
  })

  it('does not log opening a gig from a profile as a search click', async () => {
    fetchGigsPaged.mockResolvedValue({ count: 1, results: [GIG] })
    renderProfile()
    ;(await screen.findByRole('link', { name: 'Monthly bookkeeping' })).click()
    expect(logSearchClick).not.toHaveBeenCalled()
  })

  it('no longer shows the old placeholder or an em dash', async () => {
    fetchGigsPaged.mockResolvedValue({ count: 0, results: [] })
    const { container } = renderProfile()
    await screen.findByText(/no gigs open/)
    expect(container.textContent).not.toContain('Sprint 2')
    expect(container.textContent).not.toContain('—')
  })
})
