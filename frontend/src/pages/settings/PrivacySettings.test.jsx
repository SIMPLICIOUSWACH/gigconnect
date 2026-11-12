import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { deleteAccount } from '../../api/settings'
import PrivacySettings from './PrivacySettings'

const logout = vi.fn()
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ logout }) }))
vi.mock('../../api/settings', async (importOriginal) => ({ ...(await importOriginal()), deleteAccount: vi.fn() }))
vi.mock('../../api/profile', async (importOriginal) => ({
  ...(await importOriginal()),
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
