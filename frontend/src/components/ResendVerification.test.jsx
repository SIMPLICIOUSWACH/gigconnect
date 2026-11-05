import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { resendVerification } from '../api/auth'
import Login from '../pages/Login'
import ResendVerification from './ResendVerification'

vi.mock('../api/auth', () => ({ resendVerification: vi.fn() }))
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ login: vi.fn() }) }))

describe('ResendVerification', () => {
  beforeEach(() => vi.clearAllMocks())

  it('sends for the given address and shows the answer', async () => {
    resendVerification.mockResolvedValue({ detail: "We've sent it a new link." })
    render(<ResendVerification email="a@example.com" />)
    fireEvent.click(screen.getByRole('button', { name: 'Resend verification email' }))
    expect(await screen.findByRole('status')).toHaveTextContent("We've sent it a new link.")
    expect(resendVerification).toHaveBeenCalledWith('a@example.com')
  })

  it('signed in, sends without an address', async () => {
    resendVerification.mockResolvedValue({ detail: 'Sent.' })
    render(<ResendVerification />)
    fireEvent.click(screen.getByRole('button', { name: 'Resend verification email' }))
    await screen.findByText('Sent.')
    expect(resendVerification).toHaveBeenCalledWith(undefined)
  })

  it('shows the server message when sending failed', async () => {
    resendVerification.mockRejectedValue({ response: { status: 503, data: { detail: "We couldn't send the email." } } })
    render(<ResendVerification />)
    fireEvent.click(screen.getByRole('button', { name: 'Resend verification email' }))
    expect(await screen.findByRole('status')).toHaveTextContent("We couldn't send the email.")
  })

  it('explains the limit', async () => {
    resendVerification.mockRejectedValue({ response: { status: 429, data: {} } })
    render(<ResendVerification />)
    fireEvent.click(screen.getByRole('button', { name: 'Resend verification email' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Wait a while')
  })
})

describe('Login after registering', () => {
  function renderLogin(state) {
    return render(
      <MemoryRouter initialEntries={[{ pathname: '/login', state }]}>
        <Login />
      </MemoryRouter>
    )
  }

  it("says the email couldn't be sent and offers Resend", async () => {
    resendVerification.mockResolvedValue({ detail: 'If an account with that email still needs verifying, we sent it.' })
    renderLogin({ registered: true, emailSent: false, email: 'new@example.com' })
    expect(screen.getByText(/we couldn't send the email\. Try Resend\./)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Resend' }))
    await screen.findByText(/we sent it/)
    expect(resendVerification).toHaveBeenCalledWith('new@example.com')
  })

  it('says to check the inbox when the email went out', () => {
    renderLogin({ registered: true, emailSent: true, email: 'new@example.com' })
    expect(screen.getByText(/Check your email to verify/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: "Didn't get it? Resend" })).toBeInTheDocument()
  })
})
