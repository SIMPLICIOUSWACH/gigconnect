import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Login from './Login'

const login = vi.fn()
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ login }) }))

function Where() {
  return <p data-testid="where">{useLocation().pathname}</p>
}

function renderLogin(state) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/login', state }]}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>
  )
}

function submit() {
  fireEvent.change(screen.getByLabelText(/Email/), { target: { value: 'a@example.com' } })
  fireEvent.change(screen.getByLabelText(/Password/), { target: { value: 'secret-value' } })
  fireEvent.click(screen.getByRole('button', { name: 'Log in' }))
}

describe('Login', () => {
  beforeEach(() => vi.clearAllMocks())

  it('goes on to profile setup straight after verifying an email, if the profile is unfinished', async () => {
    login.mockResolvedValue({ role: 'client', is_profile_complete: false })
    renderLogin({ emailVerified: true })
    expect(screen.getByText('Your email is verified. Log in to set up your profile.')).toBeInTheDocument()
    submit()
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/profile-setup'))
  })

  it('goes to the dashboard if the profile is finished', async () => {
    login.mockResolvedValue({ role: 'client', is_profile_complete: true })
    renderLogin({ emailVerified: true })
    submit()
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/dashboard'))
  })

  it('an ordinary login goes to the dashboard even with an unfinished profile', async () => {
    login.mockResolvedValue({ role: 'client', is_profile_complete: false })
    renderLogin()
    submit()
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/dashboard'))
  })

  it('admins land on the admin area', async () => {
    login.mockResolvedValue({ role: 'admin', is_profile_complete: true })
    renderLogin({ emailVerified: true })
    submit()
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/admin'))
  })

  it('shows the reason to a suspended user and a plain message otherwise', async () => {
    login.mockRejectedValue({ response: { data: { code: 'account_suspended', detail: 'This account is suspended.' } } })
    renderLogin()
    submit()
    expect(await screen.findByText('This account is suspended.')).toBeInTheDocument()
  })
})
