import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Dashboard from './Dashboard'
import { fetchRecommendations } from '../api/recommendations'

vi.mock('../api/auth', () => ({ sendOtp: vi.fn() }))
vi.mock('../api/gigs', () => ({ logRecommendationClick: vi.fn(), logSearchClick: vi.fn() }))
vi.mock('../api/recommendations', () => ({ fetchRecommendations: vi.fn() }))

let mockUser
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

const makeUser = (role) => ({
  full_name: 'Test User',
  email: 'test@example.com',
  role,
  is_email_verified: true,
  is_phone_verified: true,
  is_profile_complete: true,
  profile: { verification_status: 'unverified' },
})

const emptyAnswer = {
  available: false,
  reason: 'disabled',
  cold_start: null,
  model: null,
  count: 0,
  page: 1,
  page_size: 4,
  total_pages: 0,
  next: null,
  previous: null,
  results: [],
}

function renderDashboard(role) {
  mockUser = makeUser(role)
  fetchRecommendations.mockResolvedValue(emptyAnswer)
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  )
}

describe('Dashboard recommendations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows Recommended for You to a freelancer, asking for four gigs', async () => {
    renderDashboard('freelancer')
    expect(screen.getByRole('heading', { name: 'Recommended for You' })).toBeInTheDocument()
    expect(await screen.findByText(/switched off for now/)).toBeInTheDocument()
    expect(fetchRecommendations).toHaveBeenCalledWith({ page_size: 4 })
  })

  it('does not show it to a client, and does not ask the server for it', () => {
    renderDashboard('client')
    expect(screen.queryByRole('heading', { name: 'Recommended for You' })).not.toBeInTheDocument()
    expect(fetchRecommendations).not.toHaveBeenCalled()
  })
})
