import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchMyGigs, updateGigStatus } from '../../api/gigs'
import { createReview, updateReview } from '../../api/reviews'
import MyGigs from './MyGigs'

vi.mock('../../api/gigs', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchMyGigs: vi.fn(),
  updateGigStatus: vi.fn(),
  deleteGig: vi.fn(),
}))
vi.mock('../../api/reviews', async (importOriginal) => ({
  ...(await importOriginal()),
  createReview: vi.fn(),
  updateReview: vi.fn(),
}))

const GIG = {
  id: 'g1',
  title: 'Logo for a bakery',
  status: 'in_progress',
  category: { name: 'Design & Creative' },
  budget_min: '1000.00',
  budget_max: '2000.00',
  deadline: '2026-12-30',
  application_count: 3,
  pending_application_count: 0,
  moderation_status: 'visible',
  chats: [{ conversation_id: 'c1', freelancer_name: 'Otieno Designs', started: true }],
  rating: null,
}

const COMPLETED = {
  ...GIG,
  status: 'completed',
  rating: { freelancer_id: 'u2', freelancer_name: 'Otieno Designs', can_rate: true, can_edit: false, review: null },
}

function renderPage() {
  return render(
    <MemoryRouter>
      <MyGigs />
    </MemoryRouter>
  )
}

async function openCompleteDialog() {
  renderPage()
  fireEvent.click(await screen.findByRole('button', { name: 'Mark as completed' }))
  return screen.findByRole('dialog', { name: 'Mark "Logo for a bakery" as completed?' })
}

describe('Completing a gig', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchMyGigs.mockResolvedValue([GIG])
    updateGigStatus.mockResolvedValue({})
    createReview.mockResolvedValue({})
  })

  it('completes without a rating when the rating is skipped', async () => {
    await openCompleteDialog()
    expect(screen.getByRole('radiogroup', { name: 'Your rating of Otieno Designs' })).toBeInTheDocument()
    fetchMyGigs.mockResolvedValue([COMPLETED])
    fireEvent.click(screen.getAllByRole('button', { name: 'Mark as completed' }).at(-1))
    await waitFor(() => expect(updateGigStatus).toHaveBeenCalledWith('g1', 'completed'))
    expect(createReview).not.toHaveBeenCalled()
    expect(await screen.findByText('Gig completed.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Rate Otieno Designs' })).toBeInTheDocument()
  })

  it('completes and sends the rating when stars are chosen', async () => {
    await openCompleteDialog()
    fireEvent.click(screen.getByRole('radio', { name: '5 stars' }))
    fireEvent.change(screen.getByLabelText(/^Review/), { target: { value: '  Brilliant and fast.  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Complete and rate' }))
    await waitFor(() => expect(createReview).toHaveBeenCalledWith('g1', { rating: 5, text: 'Brilliant and fast.' }))
    expect(updateGigStatus).toHaveBeenCalledWith('g1', 'completed')
    expect(await screen.findByText('Gig completed, and your rating of Otieno Designs was saved.')).toBeInTheDocument()
  })

  it('asks for stars when there are words but no rating', async () => {
    await openCompleteDialog()
    fireEvent.change(screen.getByLabelText(/^Review/), { target: { value: 'Good.' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Mark as completed' }).at(-1))
    expect(await screen.findByRole('alert')).toHaveTextContent('Choose 1 to 5 stars')
    expect(updateGigStatus).not.toHaveBeenCalled()
  })

  it('says so when the gig completed but the rating was not saved, and keeps Rate available', async () => {
    createReview.mockRejectedValue(new Error('offline'))
    await openCompleteDialog()
    fireEvent.click(screen.getByRole('radio', { name: '4 stars' }))
    fetchMyGigs.mockResolvedValue([COMPLETED])
    fireEvent.click(screen.getByRole('button', { name: 'Complete and rate' }))
    expect(
      await screen.findByText("Gig completed, but your rating wasn't saved. Try again from My gigs.")
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Rate Otieno Designs' })).toBeInTheDocument()
  })
})

describe('Rating later from My gigs', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchMyGigs.mockResolvedValue([COMPLETED])
  })

  it('rates a completed gig, and stars are required', async () => {
    createReview.mockResolvedValue({})
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Rate Otieno Designs' }))
    fireEvent.click(screen.getByRole('button', { name: 'Send rating' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Choose 1 to 5 stars.')
    fireEvent.click(screen.getByRole('radio', { name: '3 stars' }))
    fireEvent.click(screen.getByRole('button', { name: 'Send rating' }))
    await waitFor(() => expect(createReview).toHaveBeenCalledWith('g1', { rating: 3, text: '' }))
  })

  it('has no Rate button once the 14 days are over', async () => {
    fetchMyGigs.mockResolvedValue([{ ...COMPLETED, rating: { ...COMPLETED.rating, can_rate: false } }])
    renderPage()
    await screen.findByText('Logo for a bakery')
    expect(screen.queryByRole('button', { name: /Rate/ })).not.toBeInTheDocument()
  })

  it('edits an existing review while the window is open', async () => {
    updateReview.mockResolvedValue({})
    const review = { id: 'r1', rating: 4, text: 'Good.', removed: false }
    fetchMyGigs.mockResolvedValue([
      { ...COMPLETED, rating: { ...COMPLETED.rating, can_rate: false, can_edit: true, review } },
    ])
    renderPage()
    expect(await screen.findByText(/You gave Otieno Designs 4 stars/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Edit review' }))
    expect(screen.getByRole('radio', { name: '4 stars' })).toBeChecked()
    fireEvent.click(screen.getByRole('radio', { name: '5 stars' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(updateReview).toHaveBeenCalledWith('g1', { rating: 5, text: 'Good.' }))
  })
})
