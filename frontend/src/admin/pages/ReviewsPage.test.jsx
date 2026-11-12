import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchReviews, removeReview, restoreReview } from '../api'
import { ToastProvider } from '../components/Toast'
import ReviewsPage from './ReviewsPage'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchReviews: vi.fn(),
  removeReview: vi.fn(),
  restoreReview: vi.fn(),
}))

const REVIEW = {
  id: 'r1',
  gig: { id: 'g1', title: 'Logo for a bakery' },
  freelancer: { id: 'u2', full_name: 'Otieno Designs' },
  client: { id: 'u1', full_name: 'Wanjiru Bakers' },
  rating: 1,
  text: 'Rude words here.',
  freelancer_reply: '',
  moderation_status: 'visible',
  removed_reason: '',
  created_at: '2026-11-05T10:00:00Z',
}

const page = (results) => ({ count: results.length, page: 1, total_pages: 1, results })

function renderPage(path = '/admin/reviews') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ToastProvider>
        <ReviewsPage />
      </ToastProvider>
    </MemoryRouter>
  )
}

describe('Admin reviews', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchReviews.mockResolvedValue(page([REVIEW]))
  })

  it('lists reviews with the people by name and passes URL filters on', async () => {
    renderPage('/admin/reviews?rating=1&moderation=visible')
    expect(await screen.findByText('Rude words here.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Otieno Designs' })).toHaveAttribute('href', '/admin/users/u2')
    expect(fetchReviews).toHaveBeenCalledWith(expect.objectContaining({ rating: '1', moderation: 'visible', page: 1 }))
  })

  it('removes a review with a reason', async () => {
    removeReview.mockResolvedValue({ ...REVIEW, moderation_status: 'removed', removed_reason: 'Abusive language.' })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /^Remove/ }))
    const dialog = screen.getByRole('dialog', { name: 'Remove this review?' })
    fireEvent.change(dialog.querySelector('textarea'), { target: { value: 'Abusive language.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Remove review' }))
    await waitFor(() => expect(removeReview).toHaveBeenCalledWith('r1', 'Abusive language.'))
    expect(await screen.findByText('Removed: Abusive language.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Restore/ })).toBeInTheDocument()
  })

  it('restores a removed review', async () => {
    fetchReviews.mockResolvedValue(page([{ ...REVIEW, moderation_status: 'removed', removed_reason: 'Abusive.' }]))
    restoreReview.mockResolvedValue(REVIEW)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /^Restore/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Restore review' }))
    await waitFor(() => expect(restoreReview).toHaveBeenCalledWith('r1', ''))
    expect(await screen.findByRole('button', { name: /^Remove/ })).toBeInTheDocument()
  })
})
