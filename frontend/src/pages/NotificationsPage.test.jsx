import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchNotifications, markAllNotificationsRead, markNotificationRead } from '../api/notifications'
import NotificationsPage from './NotificationsPage'

vi.mock('../api/notifications', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
}))

const ITEM = {
  id: 'n1',
  title: 'Your gig was removed',
  body: 'An administrator removed your gig. Reason: Spam.',
  link: '/gigs/mine',
  is_read: false,
  created_at: '2026-10-30T10:00:00Z',
}

const page = (results, extra = {}) => ({ count: results.length, page: 1, total_pages: 1, results, ...extra })

function Where() {
  return <p data-testid="path">{useLocation().pathname}</p>
}

function renderPage() {
  return render(
    <MemoryRouter>
      <NotificationsPage />
      <Where />
    </MemoryRouter>
  )
}

describe('NotificationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchNotifications.mockResolvedValue(page([ITEM]))
    markNotificationRead.mockResolvedValue({})
    markAllNotificationsRead.mockResolvedValue({ marked: 1 })
  })

  it('shows the title, the body with the reason, and that it is unread', async () => {
    renderPage()
    expect(await screen.findByText('Your gig was removed')).toBeInTheDocument()
    expect(screen.getByText(/Reason: Spam\./)).toBeInTheDocument()
    expect(screen.getByText('Unread:')).toBeInTheDocument()
  })

  it('filters to unread ones', async () => {
    renderPage()
    await screen.findByText('Your gig was removed')
    fireEvent.click(screen.getByRole('button', { name: 'Unread' }))
    await waitFor(() => expect(fetchNotifications).toHaveBeenLastCalledWith(expect.objectContaining({ unread: true, page: 1 })))
    expect(screen.getByRole('button', { name: 'Unread' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('opening one marks it read and follows its link', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Your gig was removed/ }))
    await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/gigs/mine'))
    expect(markNotificationRead).toHaveBeenCalledWith('n1')
  })

  it('still follows the link if marking it read fails', async () => {
    markNotificationRead.mockRejectedValue(new Error('offline'))
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Your gig was removed/ }))
    await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/gigs/mine'))
  })

  it('marks all as read and loads the list again', async () => {
    renderPage()
    await screen.findByText('Your gig was removed')
    fireEvent.click(screen.getByRole('button', { name: 'Mark all as read' }))
    await waitFor(() => expect(fetchNotifications).toHaveBeenCalledTimes(2))
    expect(markAllNotificationsRead).toHaveBeenCalled()
  })

  it('has an empty state that links to the settings', async () => {
    fetchNotifications.mockResolvedValue(page([]))
    renderPage()
    expect(await screen.findByText('No notifications yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'notification settings' })).toHaveAttribute('href', '/settings/notifications')
  })

  it('shows an error when loading fails', async () => {
    fetchNotifications.mockRejectedValue(new Error('offline'))
    renderPage()
    expect(await screen.findByText('Could not load your notifications.')).toBeInTheDocument()
  })

  it('pages through long lists', async () => {
    fetchNotifications.mockResolvedValue(page([ITEM], { total_pages: 3, next: 'x', previous: null }))
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Next' }))
    await waitFor(() => expect(fetchNotifications).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })))
  })
})
