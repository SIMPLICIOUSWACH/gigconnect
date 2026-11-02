import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  announceNotificationsChanged,
  fetchNotifications,
  fetchUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
} from '../../api/notifications'
import NotificationBell, { POLL_MS } from './NotificationBell'

vi.mock('../../api/notifications', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchNotifications: vi.fn(),
  fetchUnreadCount: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
}))

const ITEM = {
  id: 'n1',
  title: 'New application for "Logo"',
  body: 'Otieno applied.',
  link: '/gigs/g1/applicants',
  is_read: false,
  created_at: '2026-10-30T10:00:00Z',
}

function Where() {
  return <p data-testid="path">{useLocation().pathname}</p>
}

function renderBell() {
  return render(
    <MemoryRouter>
      <NotificationBell />
      <Where />
    </MemoryRouter>
  )
}

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchUnreadCount.mockResolvedValue(3)
    fetchNotifications.mockResolvedValue({ results: [ITEM] })
    markNotificationRead.mockResolvedValue({})
    markAllNotificationsRead.mockResolvedValue({ marked: 3 })
  })

  afterEach(() => vi.useRealTimers())

  it('shows the unread count in its label and badge', async () => {
    renderBell()
    expect(await screen.findByRole('button', { name: 'Notifications, 3 unread' })).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('has no badge with nothing unread', async () => {
    fetchUnreadCount.mockResolvedValue(0)
    renderBell()
    await waitFor(() => expect(fetchUnreadCount).toHaveBeenCalled())
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('checks again on a timer, so a new notification appears without a reload', async () => {
    vi.useFakeTimers()
    renderBell()
    await act(async () => {})
    expect(fetchUnreadCount).toHaveBeenCalledTimes(1)
    await act(async () => {
      vi.advanceTimersByTime(POLL_MS)
    })
    expect(fetchUnreadCount).toHaveBeenCalledTimes(2)
  })

  it('checks again when the notifications page changes something', async () => {
    renderBell()
    await waitFor(() => expect(fetchUnreadCount).toHaveBeenCalledTimes(1))
    act(() => announceNotificationsChanged())
    await waitFor(() => expect(fetchUnreadCount).toHaveBeenCalledTimes(2))
  })

  it('opening an item marks it read and goes to its link', async () => {
    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: 'Notifications, 3 unread' }))
    fireEvent.click(await screen.findByRole('button', { name: /New application for "Logo"/ }))
    expect(markNotificationRead).toHaveBeenCalledWith('n1')
    await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/gigs/g1/applicants'))
    expect(screen.queryByRole('region', { name: 'Latest notifications' })).not.toBeInTheDocument()
  })

  it('marks everything as read', async () => {
    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: 'Notifications, 3 unread' }))
    const markAll = await screen.findByRole('button', { name: 'Mark all as read' })
    fetchUnreadCount.mockResolvedValue(0)
    fireEvent.click(markAll)
    expect(await screen.findByRole('button', { name: 'Notifications' })).toBeInTheDocument()
    expect(markAllNotificationsRead).toHaveBeenCalled()
  })

  it('closes on Esc and links to the full page', async () => {
    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: 'Notifications, 3 unread' }))
    expect(await screen.findByRole('link', { name: 'See all notifications' })).toHaveAttribute('href', '/notifications')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('link', { name: 'See all notifications' })).not.toBeInTheDocument()
  })

  it('says so when there is nothing yet', async () => {
    fetchNotifications.mockResolvedValue({ results: [] })
    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: 'Notifications, 3 unread' }))
    expect(await screen.findByText('Nothing here yet.')).toBeInTheDocument()
  })
})
