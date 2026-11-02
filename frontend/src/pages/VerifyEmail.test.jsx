import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { verifyEmail } from '../api/auth'
import VerifyEmail from './VerifyEmail'

vi.mock('../api/auth', () => ({ verifyEmail: vi.fn() }))

const refreshUser = vi.fn()
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ refreshUser }) }))

function Where() {
  const location = useLocation()
  return <p data-testid="where">{`${location.pathname} ${JSON.stringify(location.state)}`}</p>
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/verify-email/abc']}>
      <Routes>
        <Route path="/verify-email/:token" element={<VerifyEmail />} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('VerifyEmail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    verifyEmail.mockResolvedValue({ detail: 'Email verified successfully.' })
  })

  it('sends a signed-in user with an unfinished profile to profile setup', async () => {
    refreshUser.mockResolvedValue({ is_profile_complete: false })
    renderPage()
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/profile-setup'))
    expect(verifyEmail).toHaveBeenCalledWith('abc')
  })

  it('sends someone who is not signed in to log in, remembering their email was just verified', async () => {
    refreshUser.mockResolvedValue(null)
    renderPage()
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/login {"emailVerified":true}'))
  })

  it('just confirms it for a user whose profile is already finished', async () => {
    refreshUser.mockResolvedValue({ is_profile_complete: true })
    renderPage()
    expect(await screen.findByText('Email verified successfully.')).toBeInTheDocument()
  })

  it('shows the error for a bad link and goes nowhere', async () => {
    verifyEmail.mockRejectedValue({ response: { data: { detail: 'Invalid verification link.' } } })
    renderPage()
    expect(await screen.findByText('Invalid verification link.')).toBeInTheDocument()
    expect(refreshUser).not.toHaveBeenCalled()
  })
})
