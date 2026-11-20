import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { deleteUser, fetchDeletePreview, fetchUser, fetchUsers } from '../api'
import { ToastProvider } from '../components/Toast'
import UserDetailPage from './UserDetailPage'
import UsersPage from './UsersPage'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchUser: vi.fn(),
  fetchUsers: vi.fn(),
  fetchDeletePreview: vi.fn(),
  deleteUser: vi.fn(),
  suspendUser: vi.fn(),
}))

const USER = {
  id: 'u1',
  full_name: 'Otieno Designs',
  email: 'otieno@example.com',
  role: 'freelancer',
  status: 'suspended',
  suspended_at: '2026-11-10T10:00:00Z',
  suspended_reason: 'Fraud reports.',
  verification_status: 'verified',
  is_email_verified: true,
  is_synthetic: false,
  created_at: '2026-01-01T10:00:00Z',
  deletion: null,
  phone: '254711000001',
  profile: null,
  gigs: [],
  applications: [],
  history: [],
}

const PREVIEW = {
  can_delete: true,
  refusal: null,
  active_work: [],
  open_gigs_closed: 0,
  applicants_notified: 0,
  applications_emptied: 3,
  id_files_deleted: 2,
  id_number_deleted: true,
  conversations_read_only: 1,
  notifications_deleted: 4,
  gig_history_deleted: 7,
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/admin/users/u1']}>
      <ToastProvider>
        <Routes>
          <Route path="/admin/users/:id" element={<UserDetailPage />} />
          <Route path="/admin/users" element={<p>Users list</p>} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  )
}

async function openDialog() {
  renderDetail()
  fireEvent.click(await screen.findByRole('button', { name: 'Delete account permanently' }))
  return screen.findByRole('dialog', { name: 'Delete this account permanently?' })
}

const confirmButton = () => screen.getAllByRole('button', { name: 'Delete account permanently' }).at(-1)

describe('Deleting a user', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchUser.mockResolvedValue(USER)
    fetchDeletePreview.mockResolvedValue(PREVIEW)
    deleteUser.mockResolvedValue({ detail: 'Account deleted.', summary: {} })
  })

  it('asks to suspend an active account first', async () => {
    fetchUser.mockResolvedValue({ ...USER, status: 'active' })
    renderDetail()
    expect(await screen.findByText(/Suspend this account first to delete it/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Delete account permanently' })).not.toBeInTheDocument()
  })

  it('has no danger zone for an admin', async () => {
    fetchUser.mockResolvedValue({ ...USER, role: 'admin', status: 'active' })
    renderDetail()
    await screen.findByRole('heading', { name: 'Otieno Designs' })
    expect(screen.queryByRole('heading', { name: 'Danger zone' })).not.toBeInTheDocument()
  })

  it('shows what will happen and keeps Confirm disabled until the reason and the exact email are given', async () => {
    await openDialog()
    expect(await screen.findByText('3 applications will be emptied, and open ones withdrawn.')).toBeInTheDocument()
    expect(screen.getByText(/ID documents, selfie and ID number deleted/)).toBeInTheDocument()
    expect(screen.getByText(/can't be recovered/)).toBeInTheDocument()
    expect(confirmButton()).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: 'Fraud.' } })
    fireEvent.change(screen.getByLabelText(/to confirm/), { target: { value: 'Otieno@example.com' } })
    expect(confirmButton()).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/to confirm/), { target: { value: 'otieno@example.com' } })
    expect(confirmButton()).toBeEnabled()
  })

  it('needs the box ticked when there is work in progress, then deletes and goes back to the list', async () => {
    fetchDeletePreview.mockResolvedValue({
      ...PREVIEW,
      active_work: [{ gig_id: 'g1', title: 'Shop signage', as: 'freelancer', other_party: 'Wanjiru Bakers' }],
    })
    await openDialog()
    expect(await screen.findByText(/"Shop signage"/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: 'Fraud.' } })
    fireEvent.change(screen.getByLabelText(/to confirm/), { target: { value: 'otieno@example.com' } })
    expect(confirmButton()).toBeDisabled()
    fireEvent.click(screen.getByLabelText('I understand: close these gigs/contracts'))
    expect(screen.getByText('1 in-progress gig will be closed, and the other person told.')).toBeInTheDocument()
    fireEvent.click(confirmButton())
    await waitFor(() =>
      expect(deleteUser).toHaveBeenCalledWith('u1', { reason: 'Fraud.', confirm_email: 'otieno@example.com', force: true })
    )
    expect(await screen.findByText('Users list')).toBeInTheDocument()
    expect(screen.getByText("Otieno Designs's account was deleted.")).toBeInTheDocument()
  })

  it('shows why the server refused', async () => {
    deleteUser.mockRejectedValue({ response: { data: { detail: "The email you typed doesn't match this account's email." } } })
    await openDialog()
    await screen.findByText(/3 applications/)
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: 'Fraud.' } })
    fireEvent.change(screen.getByLabelText(/to confirm/), { target: { value: 'otieno@example.com' } })
    fireEvent.click(confirmButton())
    expect(await screen.findByRole('alert')).toHaveTextContent("doesn't match")
  })
})

describe('Deleted accounts in the list', () => {
  it('are read-only rows with the masked email, date and admin', async () => {
    fetchUsers.mockResolvedValue({
      count: 1,
      page: 1,
      total_pages: 1,
      results: [
        {
          ...USER,
          full_name: 'Deleted User',
          email: 'deleted-u1@gigconnect.invalid',
          status: 'deleted',
          deletion: { label: 'Deleted user · o***@example.com', deleted_at: '2026-11-12T10:00:00Z', by: 'Asha Admin' },
        },
      ],
    })
    render(
      <MemoryRouter initialEntries={['/admin/users?status=deleted']}>
        <UsersPage />
      </MemoryRouter>
    )
    expect(await screen.findByText(/Deleted user · o\*\*\*@example.com · deleted .* by Asha Admin/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Deleted/ })).not.toBeInTheDocument()
    expect(screen.queryByText('deleted-u1@gigconnect.invalid')).not.toBeInTheDocument()
  })
})
