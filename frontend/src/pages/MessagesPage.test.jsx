import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchConversation, fetchConversations, fetchMessageUnreadCount, fetchMessages } from '../api/messages'
import MessagesNavLink from '../components/messages/MessagesNavLink'
import MessagesPage from './MessagesPage'

let mockUser = { role: 'client' }
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))
vi.mock('../api/messages', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchConversations: vi.fn(),
  fetchConversation: vi.fn(),
  fetchMessages: vi.fn(),
  fetchMessageUnreadCount: vi.fn(),
  markConversationRead: vi.fn(() => Promise.resolve({})),
}))

const ROW = {
  id: 'c1',
  gig: { id: 'g1', title: 'Logo for a bakery' },
  other: { id: 'u2', full_name: 'Otieno Designs', role: 'freelancer' },
  my_role: 'client',
  hired_at: '2026-11-03T09:00:00Z',
  first_message_at: '2026-11-03T10:00:00Z',
  last_message_at: '2026-11-03T10:00:00Z',
  last_message: { body: 'Sounds good', from_me: false, created_at: '2026-11-03T10:00:00Z' },
  unread_count: 2,
  read_only_reason: null,
  waiting_for_client: false,
  can_send: true,
}

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/messages" element={<MessagesPage />} />
        <Route path="/messages/:id" element={<MessagesPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('MessagesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUser = { role: 'client' }
    fetchConversations.mockResolvedValue({ results: [ROW] })
    fetchConversation.mockResolvedValue(ROW)
    fetchMessages.mockResolvedValue({ results: [], has_earlier: false, seen_up_to: null })
  })

  it('lists chats with the last message and the unread count', async () => {
    renderAt('/messages')
    const link = await screen.findByRole('link', { name: /Otieno Designs/ })
    expect(link).toHaveAttribute('href', '/messages/c1')
    expect(link).toHaveTextContent('Sounds good')
    expect(link).toHaveTextContent('2 unread')
    expect(screen.getByText('Choose a chat')).toBeInTheDocument()
  })

  it('has an empty state for each role', async () => {
    fetchConversations.mockResolvedValue({ results: [] })
    renderAt('/messages')
    expect(await screen.findByText('When you hire a freelancer, you can message them here.')).toBeInTheDocument()
  })

  it('opens the chat and marks it as the current one', async () => {
    renderAt('/messages/c1')
    expect(await screen.findByRole('heading', { name: 'Otieno Designs' })).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByRole('link', { name: /Otieno Designs/ })).toHaveAttribute('aria-current', 'page')
    )
    expect(screen.getByRole('link', { name: 'Back to messages' })).toHaveAttribute('href', '/messages')
  })
})

describe('MessagesNavLink', () => {
  const navClass = () => 'nav'

  it('shows the unread count', async () => {
    fetchMessageUnreadCount.mockResolvedValue(4)
    render(
      <MemoryRouter>
        <MessagesNavLink className={navClass} />
      </MemoryRouter>
    )
    expect(await screen.findByRole('link', { name: 'Messages 4 unread' })).toHaveAttribute('href', '/messages')
  })

  it('has no badge with nothing unread', async () => {
    fetchMessageUnreadCount.mockResolvedValue(0)
    render(
      <MemoryRouter>
        <MessagesNavLink className={navClass} />
      </MemoryRouter>
    )
    await waitFor(() => expect(fetchMessageUnreadCount).toHaveBeenCalled())
    expect(screen.getByRole('link', { name: 'Messages' })).toBeInTheDocument()
  })
})
