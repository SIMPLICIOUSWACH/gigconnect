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

describe('GigCard Direction B details', () => {
  beforeEach(() => vi.clearAllMocks())

  const soon = (days) => {
    const d = new Date()
    d.setDate(d.getDate() + days)
    return d.toISOString().slice(0, 10)
  }

  it('shows the category, the client initials and name, and the terms with the apply-by date', () => {
    renderCard({ gig: { ...GIG, client_name: 'Baraka Traders' } })
    expect(screen.getByText('Design & Creative')).toBeInTheDocument()
    expect(screen.getByText('BT')).toBeInTheDocument()
    expect(screen.getByText('Baraka Traders')).toBeInTheDocument()
    expect(screen.getByText('Fixed price · Apply by 1 Jan')).toBeInTheDocument()
  })

  it('says Negotiable when the budget is negotiable', () => {
    renderCard({ gig: { ...GIG, is_negotiable: true } })
    expect(screen.getByText(/^Negotiable · Apply by/)).toBeInTheDocument()
  })

  it('marks the gig Urgent when applications close within three days', () => {
    renderCard({ gig: { ...GIG, application_deadline: soon(2) } })
    expect(screen.getByText('Urgent')).toBeInTheDocument()
  })

  it('does not mark it Urgent when applications close later', () => {
    renderCard({ gig: { ...GIG, application_deadline: soon(10) } })
    expect(screen.queryByText('Urgent')).not.toBeInTheDocument()
  })

  it('the Apply button opens the gig and logs the click like the title does', () => {
    renderCard({ query: 'logo', position: 2 })
    const apply = screen.getByRole('link', { name: 'Apply: Logo for a cafe' })
    expect(apply).toHaveAttribute('href', '/gigs/gig-1')
    fireEvent.click(apply)
    expect(logSearchClick).toHaveBeenCalledWith('gig-1', { query: 'logo', position: 2 })
  })
})
