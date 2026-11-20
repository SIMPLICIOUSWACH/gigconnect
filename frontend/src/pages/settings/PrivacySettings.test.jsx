import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { updateFreelancerProfile } from '../../api/profile'
import { deleteAccount } from '../../api/settings'
import PrivacySettings from './PrivacySettings'

const logout = vi.fn()
let mockUser
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ logout, user: mockUser, refreshUser: vi.fn() }) }))
vi.mock('../../api/settings', async (importOriginal) => ({ ...(await importOriginal()), deleteAccount: vi.fn() }))
vi.mock('../../api/profile', async (importOriginal) => ({
  ...(await importOriginal()),
  updateFreelancerProfile: vi.fn(() => Promise.resolve({})),
  fetchPrivacyInfo: vi.fn(() => Promise.resolve({ contact_email: '', id_image_retention_days: 90 })),
}))

function confirmDelete() {
  render(
    <MemoryRouter>
      <PrivacySettings />
    </MemoryRouter>
  )
  fireEvent.click(screen.getByRole('button', { name: 'Delete my account' }))
  fireEvent.change(screen.getByLabelText('Confirm your password'), { target: { value: 'secret' } })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm delete' }))
}

describe('Deleting your account', () => {
  beforeEach(() => vi.clearAllMocks())

  it('lists the in-progress work that blocks it', async () => {
    deleteAccount.mockRejectedValue({
      response: {
        data: {
          code: 'active_work',
          detail: 'Finish or close these first, or contact support.',
          active_work: [{ gig_id: 'g1', title: 'Shop signage', as: 'client', other_party: 'Otieno Designs' }],
        },
      },
    })
    confirmDelete()
    expect(await screen.findByText('Finish or close these first, or contact support.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Shop signage' })).toHaveAttribute('href', '/gigs/g1')
    expect(screen.getByRole('list', { name: 'Work in progress' })).toHaveTextContent('with Otieno Designs')
    expect(logout).not.toHaveBeenCalled()
  })

  it('logs out once deleted', async () => {
    deleteAccount.mockResolvedValue({ detail: 'Account deleted.' })
    confirmDelete()
    await vi.waitFor(() => expect(logout).toHaveBeenCalled())
  })
})

describe('Show my profile in Find freelancers', () => {
  beforeEach(() => vi.clearAllMocks())

  function renderAs(user) {
    mockUser = user
    render(
      <MemoryRouter>
        <PrivacySettings />
      </MemoryRouter>
    )
  }

  it('is a switch for freelancers that saves as soon as it changes', async () => {
    renderAs({ role: 'freelancer', profile: { search_visible: true } })
    const toggle = screen.getByRole('switch', { name: 'Show my profile in Find freelancers' })
    expect(toggle).toHaveAttribute('aria-checked', 'true')
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-checked', 'false')
    await vi.waitFor(() => expect(updateFreelancerProfile).toHaveBeenCalledWith({ search_visible: false }))
  })

  it('is not shown to clients', () => {
    renderAs({ role: 'client', profile: {} })
    expect(screen.queryByRole('switch', { name: 'Show my profile in Find freelancers' })).not.toBeInTheDocument()
  })
})
