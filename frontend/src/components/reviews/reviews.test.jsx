import { useState } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchFreelancerReviews, replyToReview } from '../../api/reviews'
import RatingSummary from './RatingSummary'
import ReviewList from './ReviewList'
import StarInput from './StarInput'

vi.mock('../../api/reviews', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchFreelancerReviews: vi.fn(),
  replyToReview: vi.fn(),
}))

function Stars({ start = 0 }) {
  const [value, setValue] = useState(start)
  return <StarInput value={value} onChange={setValue} label="Your rating" />
}

const checked = () => screen.queryByRole('radio', { checked: true })

describe('StarInput', () => {
  it('is a labelled radio group with one star per value', () => {
    render(<Stars />)
    expect(screen.getByRole('radiogroup', { name: 'Your rating' })).toBeInTheDocument()
    expect(screen.getAllByRole('radio').map((star) => star.getAttribute('aria-label'))).toEqual([
      '1 star',
      '2 stars',
      '3 stars',
      '4 stars',
      '5 stars',
    ])
    expect(checked()).toBeNull()
  })

  it('is chosen with the keyboard: arrows move and choose, Home and End jump, Space chooses', () => {
    render(<Stars />)
    const first = screen.getByRole('radio', { name: '1 star' })
    first.focus()
    fireEvent.keyDown(first, { key: ' ' })
    expect(checked()).toHaveAccessibleName('1 star')
    fireEvent.keyDown(document.activeElement, { key: 'ArrowRight' })
    fireEvent.keyDown(document.activeElement, { key: 'ArrowRight' })
    expect(checked()).toHaveAccessibleName('3 stars')
    expect(document.activeElement).toBe(screen.getByRole('radio', { name: '3 stars' }))
    fireEvent.keyDown(document.activeElement, { key: 'ArrowLeft' })
    expect(checked()).toHaveAccessibleName('2 stars')
    fireEvent.keyDown(document.activeElement, { key: 'End' })
    expect(checked()).toHaveAccessibleName('5 stars')
    fireEvent.keyDown(document.activeElement, { key: 'ArrowRight' })
    expect(checked()).toHaveAccessibleName('5 stars') // stops at 5
    fireEvent.keyDown(document.activeElement, { key: 'Home' })
    expect(checked()).toHaveAccessibleName('1 star')
  })

  it('has one tab stop: the chosen star', () => {
    render(<Stars start={4} />)
    const stops = screen.getAllByRole('radio').filter((star) => star.tabIndex === 0)
    expect(stops).toHaveLength(1)
    expect(stops[0]).toHaveAccessibleName('4 stars')
  })

  it('is chosen with a click', () => {
    render(<Stars />)
    fireEvent.click(screen.getByRole('radio', { name: '4 stars' }))
    expect(checked()).toHaveAccessibleName('4 stars')
  })
})

describe('RatingSummary', () => {
  it('shows the average and the count', () => {
    render(<RatingSummary average="4.60" count={12} />)
    expect(screen.getByText('4.6')).toBeInTheDocument()
    expect(screen.getByText('· 12 reviews')).toBeInTheDocument()
  })

  it('says New for someone with no reviews, never 0 stars', () => {
    render(<RatingSummary average={null} count={0} />)
    expect(screen.getByText('New')).toBeInTheDocument()
    expect(screen.queryByText(/0/)).not.toBeInTheDocument()
  })
})

const REVIEW = {
  id: 'r1',
  rating: 4,
  text: 'Solid work, on time.',
  gig_title: 'Logo for a bakery',
  client_name: 'Wanjiru Bakers',
  created_at: '2026-11-05T10:00:00Z',
  edited: false,
  reply: '',
  reply_at: null,
  can_reply: false,
}

describe('ReviewList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchFreelancerReviews.mockResolvedValue({ results: [REVIEW], page: 1, total_pages: 1 })
  })

  it('lists reviews with the gig, the client, the stars and the words', async () => {
    render(<ReviewList freelancerId="u2" freelancerName="Otieno Designs" average="4.00" count={1} />)
    expect(await screen.findByText('Solid work, on time.')).toBeInTheDocument()
    expect(screen.getByText('Wanjiru Bakers')).toBeInTheDocument()
    expect(screen.getByText('For "Logo for a bakery"')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: '4 stars' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reply' })).not.toBeInTheDocument()
  })

  it('lets the rated freelancer reply once', async () => {
    fetchFreelancerReviews.mockResolvedValue({ results: [{ ...REVIEW, can_reply: true }], page: 1, total_pages: 1 })
    replyToReview.mockResolvedValue({ ...REVIEW, reply: 'Thank you!', reply_at: '2026-11-06T10:00:00Z' })
    render(<ReviewList freelancerId="u2" freelancerName="Otieno Designs" average="4.00" count={1} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Reply' }))
    fireEvent.change(screen.getByLabelText('Your reply'), { target: { value: 'Thank you!' } })
    fireEvent.click(screen.getByRole('button', { name: 'Post reply' }))
    await waitFor(() => expect(replyToReview).toHaveBeenCalledWith('r1', 'Thank you!'))
    expect(await screen.findByText('Reply from Otieno Designs')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reply' })).not.toBeInTheDocument()
  })

  it('has an empty state', async () => {
    fetchFreelancerReviews.mockResolvedValue({ results: [], page: 1, total_pages: 1 })
    render(<ReviewList freelancerId="u2" freelancerName="Otieno Designs" average={null} count={0} />)
    expect(await screen.findByText(/No reviews yet/)).toBeInTheDocument()
    expect(screen.getByText('New')).toBeInTheDocument()
  })
})
