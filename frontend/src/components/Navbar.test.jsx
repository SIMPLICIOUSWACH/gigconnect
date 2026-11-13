import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import Navbar from './Navbar'

let mockUser = null
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ user: mockUser, logout: vi.fn() }) }))
vi.mock('../api/notifications', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchUnreadCount: vi.fn(() => Promise.resolve(0)),
}))
vi.mock('../api/messages', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchMessageUnreadCount: vi.fn(() => Promise.resolve(0)),
}))

function links(role) {
  mockUser = { id: 'u1', role, full_name: 'Test Person', profile: {} }
  render(
    <MemoryRouter>
      <Navbar />
    </MemoryRouter>
  )
  const nav = screen.getByRole('navigation', { name: 'Main' })
  return [...nav.querySelectorAll('a')].map((link) => [link.textContent, link.getAttribute('href')])
}

describe('Main navigation', () => {
  it('gives clients Find freelancers instead of Find gigs', () => {
    const items = links('client')
    expect(items).toContainEqual(['Find freelancers', '/freelancers'])
    expect(items.map(([label]) => label)).not.toContain('Find gigs')
    expect(items.map(([label]) => label)).toEqual(['Dashboard', 'Find freelancers', 'My gigs', 'Messages'])
  })

  it('keeps Find gigs for freelancers, with no Find freelancers', () => {
    const labels = links('freelancer').map(([label]) => label)
    expect(labels).toContain('Find gigs')
    expect(labels).not.toContain('Find freelancers')
  })

  it('shows admins both', () => {
    const labels = links('admin').map(([label]) => label)
    expect(labels).toEqual(expect.arrayContaining(['Find gigs', 'Find freelancers', 'Admin']))
  })
})
