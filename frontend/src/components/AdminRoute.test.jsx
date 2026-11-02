import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AdminRoute from './AdminRoute'

let auth = { user: null, loading: false }
vi.mock('../context/AuthContext', () => ({ useAuth: () => auth }))

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<p>Login page</p>} />
        <Route path="/dashboard" element={<p>Dashboard</p>} />
        <Route
          path="/admin/*"
          element={
            <AdminRoute>
              <p>Admin area</p>
            </AdminRoute>
          }
        />
      </Routes>
    </MemoryRouter>
  )
}

describe('AdminRoute', () => {
  beforeEach(() => {
    auth = { user: null, loading: false }
  })

  it('sends visitors who are not logged in to the login page', () => {
    renderAt('/admin/users')
    expect(screen.getByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Admin area')).not.toBeInTheDocument()
  })

  it.each(['freelancer', 'client'])('shows a %s the 403 page, not the admin area', (role) => {
    auth = { user: { id: 'u1', role, full_name: 'Amina' }, loading: false }
    renderAt('/admin')
    expect(screen.getByRole('heading', { name: 'This page is for GigConnect admins' })).toBeInTheDocument()
    expect(screen.getByText('Error 403')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to your dashboard' })).toHaveAttribute('href', '/dashboard')
    expect(screen.queryByText('Admin area')).not.toBeInTheDocument()
  })

  it('lets an admin in', () => {
    auth = { user: { id: 'a1', role: 'admin', full_name: 'Admin' }, loading: false }
    renderAt('/admin')
    expect(screen.getByText('Admin area')).toBeInTheDocument()
  })

  it('shows nothing while the session is still loading', () => {
    auth = { user: null, loading: true }
    const { container } = renderAt('/admin')
    expect(container).toBeEmptyDOMElement()
  })
})
