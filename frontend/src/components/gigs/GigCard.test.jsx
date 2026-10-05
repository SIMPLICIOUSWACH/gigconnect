import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GigCard from './GigCard'
import { logSearchClick } from '../../api/gigs'

vi.mock('../../api/gigs', () => ({ logSearchClick: vi.fn() }))

const GIG = {
  id: 'gig-1',
  title: 'Logo for a cafe',
  client_name: 'Amina',
  category: { name: 'Design & Creative' },
  skills: [],
  budget_min: '1000',
  budget_max: '2000',
  currency: 'KES',
  deadline: '2030-01-01',
  application_deadline: '2030-01-01',
  created_at: '2026-01-01T00:00:00Z',
  is_negotiable: false,
  status: 'open',
  county: null,
  is_remote: false,
}

function renderCard(props = {}) {
  return render(
    <MemoryRouter>
      <GigCard gig={GIG} {...props} />
    </MemoryRouter>
  )
}

describe('GigCard click logging', () => {
  beforeEach(() => vi.clearAllMocks())

  it('logs a search click with the query and result position when the title is opened', () => {
    renderCard({ query: 'logo', position: 7 })
    fireEvent.click(screen.getByRole('link', { name: 'Logo for a cafe' }))
    expect(logSearchClick).toHaveBeenCalledWith('gig-1', { query: 'logo', position: 7 })
  })

  it('still logs the click when there was no search query', () => {
    renderCard({ query: '', position: 1 })
    fireEvent.click(screen.getByRole('link', { name: 'Logo for a cafe' }))
    expect(logSearchClick).toHaveBeenCalledWith('gig-1', { query: '', position: 1 })
  })

  it('does not log anything just from rendering', () => {
    renderCard({ query: 'logo', position: 3 })
    expect(logSearchClick).not.toHaveBeenCalled()
  })

  it('shows the county and remote label', () => {
    renderCard({ gig: { ...GIG, county: 'Nairobi', is_remote: true } })
    expect(screen.getByText(/Nairobi or remote/)).toBeInTheDocument()
  })
})
