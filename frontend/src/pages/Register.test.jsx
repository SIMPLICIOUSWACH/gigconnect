import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchSkills, register } from '../api/auth'
import Register from './Register'

vi.mock('../api/auth', () => ({ fetchSkills: vi.fn(), register: vi.fn(), createSkill: vi.fn() }))

const HINT = /Used for M-Pesa payments later\. We won.t send you codes\./

function renderAsClient() {
  return render(
    <MemoryRouter initialEntries={['/register?role=client']}>
      <Register />
    </MemoryRouter>
  )
}

describe('Register phone field', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchSkills.mockResolvedValue([])
    register.mockResolvedValue({})
  })

  it('is optional and explains what the number is for', () => {
    renderAsClient()
    const phone = screen.getByLabelText(/Phone \(optional\)/)
    expect(phone).not.toBeRequired()
    expect(screen.getByText(HINT)).toBeInTheDocument()
  })

  it('shows the server message for a number it refuses', async () => {
    register.mockRejectedValue({ response: { data: { phone: ['Landlines are not accepted.'] } } })
    const { container } = renderAsClient()
    fireEvent.change(screen.getByLabelText(/Full name/), { target: { value: 'A Client' } })
    fireEvent.change(screen.getByLabelText(/Email/), { target: { value: 'a@example.com' } })
    fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: 'StrongPass123!' } })
    fireEvent.change(screen.getByLabelText(/Confirm password/), { target: { value: 'StrongPass123!' } })
    fireEvent.submit(container.querySelector('form'))
    await waitFor(() => expect(screen.getByText('Landlines are not accepted.')).toBeInTheDocument())
  })
})
