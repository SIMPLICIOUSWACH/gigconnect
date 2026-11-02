import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider } from '../components/Toast'
import { fetchCategories, fetchGigs, removeGig } from '../api'
import GigsPage from './GigsPage'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchGigs: vi.fn(),
  fetchCategories: vi.fn(),
  removeGig: vi.fn(),
  restoreGig: vi.fn(),
}))

const GIG = {
  id: 'g1',
  title: 'Logo for a bakery',
  client: { id: 'c1', full_name: 'Wanjiru Bakers' },
  client_status: 'active',
  category: 'Design & Creative',
  status: 'open',
  moderation_status: 'visible',
  removed_reason: '',
  budget_min: '1000.00',
  budget_max: '2000.00',
  application_count: 3,
  created_at: '2026-10-20T10:00:00Z',
}

const page = (results) => ({ count: results.length, page: 1, total_pages: 1, next: null, previous: null, results })

function renderPage(path = '/admin/gigs') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ToastProvider>
        <GigsPage />
      </ToastProvider>
    </MemoryRouter>
  )
}

describe('GigsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchCategories.mockResolvedValue([{ slug: 'design-creative', name: 'Design & Creative' }])
    fetchGigs.mockResolvedValue(page([GIG]))
  })

  it('lists gigs with the client by name', async () => {
    renderPage()
    expect(await screen.findByRole('link', { name: 'Logo for a bakery' })).toHaveAttribute('href', '/admin/gigs/g1')
    expect(screen.getByRole('link', { name: 'Wanjiru Bakers' })).toHaveAttribute('href', '/admin/users/c1')
    expect(screen.queryByText('c1')).not.toBeInTheDocument()
  })

  it('passes filters from the URL to the API', async () => {
    renderPage('/admin/gigs?status=open&moderation=removed')
    await screen.findByRole('link', { name: 'Logo for a bakery' })
    expect(fetchGigs).toHaveBeenCalledWith(expect.objectContaining({ status: 'open', moderation: 'removed', page: 1 }))
  })

  it('removes a gig after a reason, updates the row in place and says so', async () => {
    removeGig.mockResolvedValue({ ...GIG, moderation_status: 'removed', removed_reason: 'Scam.' })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Remove Logo for a bakery' }))

    const dialog = screen.getByRole('dialog', { name: 'Remove "Logo for a bakery"?' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Remove gig' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Give a reason')
    expect(removeGig).not.toHaveBeenCalled()

    fireEvent.change(within(dialog).getByRole('textbox', { name: /Reason/ }), { target: { value: 'Scam.' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Remove gig' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(removeGig).toHaveBeenCalledWith('g1', 'Scam.')
    expect(within(screen.getByRole('table')).getByText('Removed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Restore Logo for a bakery' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('"Logo for a bakery" was removed.')
    expect(fetchGigs).toHaveBeenCalledTimes(1)
  })

  it('shows an empty state when nothing matches', async () => {
    fetchGigs.mockResolvedValue(page([]))
    renderPage()
    expect(await screen.findByText('No gigs match these filters.')).toBeInTheDocument()
  })
})
