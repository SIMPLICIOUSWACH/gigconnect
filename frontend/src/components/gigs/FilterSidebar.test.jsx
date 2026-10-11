import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FilterSidebar from './FilterSidebar'

const CATEGORIES = [
  { id: 'c1', name: 'Design & Creative', slug: 'design-creative' },
  { id: 'c2', name: 'Local Services', slug: 'local-services' },
]
const COUNTIES = [
  { value: 'Nairobi', label: 'Nairobi' },
  { value: 'Mombasa', label: 'Mombasa' },
]
const SKILLS = [
  { id: 's1', name: 'Plumbing' },
  { id: 's2', name: 'Carpentry' },
]

const NO_FILTERS = {
  q: '',
  category: '',
  skillIds: [],
  budget_min: '',
  budget_max: '',
  negotiable: false,
  includeClosed: false,
  county: '',
  remote: false,
  deadline_before: '',
  posted_within: '',
  sort: 'newest',
  page: 1,
}

function renderSidebar(filters = {}) {
  const onChange = vi.fn()
  const onClear = vi.fn()
  render(
    <FilterSidebar
      categories={CATEGORIES}
      counties={COUNTIES}
      skills={SKILLS}
      filters={{ ...NO_FILTERS, ...filters }}
      onChange={onChange}
      onClear={onClear}
    />
  )
  return { onChange, onClear }
}

describe('FilterSidebar', () => {
  beforeEach(() => vi.clearAllMocks())

  it('reports a category choice by slug', () => {
    const { onChange } = renderSidebar()
    fireEvent.click(screen.getByRole('radio', { name: 'Local Services' }))
    expect(onChange).toHaveBeenCalledWith({ category: 'local-services' })
  })

  it('clears the category with "All categories"', () => {
    const { onChange } = renderSidebar({ category: 'design-creative' })
    fireEvent.click(screen.getByRole('radio', { name: 'All categories' }))
    expect(onChange).toHaveBeenCalledWith({ category: '' })
  })

  it('reports a county choice', () => {
    const { onChange } = renderSidebar()
    fireEvent.change(screen.getByLabelText('County'), { target: { value: 'Mombasa' } })
    expect(onChange).toHaveBeenCalledWith({ county: 'Mombasa' })
  })

  it('reports the remote-only toggle', () => {
    const { onChange } = renderSidebar()
    fireEvent.click(screen.getByLabelText('Remote gigs only'))
    expect(onChange).toHaveBeenCalledWith({ remote: true })
  })

  it('adds and removes a skill from the selection', () => {
    const { onChange } = renderSidebar({ skillIds: ['s1'] })
    fireEvent.click(screen.getByRole('button', { name: 'Carpentry' }))
    expect(onChange).toHaveBeenCalledWith({ skillIds: ['s1', 's2'] })
    fireEvent.click(screen.getByRole('button', { name: 'Plumbing' }))
    expect(onChange).toHaveBeenCalledWith({ skillIds: [] })
  })

  it('marks selected skills as pressed for assistive technology', () => {
    renderSidebar({ skillIds: ['s1'] })
    expect(screen.getByRole('button', { name: 'Plumbing' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Carpentry' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('reports the budget range', () => {
    const { onChange } = renderSidebar()
    fireEvent.change(screen.getByLabelText('Minimum budget in KES'), { target: { value: '5000' } })
    expect(onChange).toHaveBeenCalledWith({ budget_min: '5000' })
    fireEvent.change(screen.getByLabelText('Maximum budget in KES'), { target: { value: '20000' } })
    expect(onChange).toHaveBeenCalledWith({ budget_max: '20000' })
  })

  it('reports the posted-within choice', () => {
    const { onChange } = renderSidebar()
    fireEvent.click(screen.getByRole('radio', { name: 'Last 7 days' }))
    expect(onChange).toHaveBeenCalledWith({ posted_within: '7' })
  })

  it('reports the deadline date', () => {
    const { onChange } = renderSidebar()
    fireEvent.change(screen.getByLabelText('Deadline before'), { target: { value: '2026-12-01' } })
    expect(onChange).toHaveBeenCalledWith({ deadline_before: '2026-12-01' })
  })

  it('reports the negotiable-only toggle', () => {
    const { onChange } = renderSidebar()
    fireEvent.click(screen.getByLabelText('Negotiable budget only'))
    expect(onChange).toHaveBeenCalledWith({ negotiable: true })
  })

  it('reports the show-closed-gigs toggle', () => {
    const { onChange } = renderSidebar()
    fireEvent.click(screen.getByLabelText('Show closed gigs'))
    expect(onChange).toHaveBeenCalledWith({ includeClosed: true })
  })

  it('shows the current values it was given', () => {
    renderSidebar({
      category: 'design-creative',
      county: 'Nairobi',
      remote: true,
      budget_min: '1000',
      includeClosed: true,
      posted_within: '30',
    })
    expect(screen.getByRole('radio', { name: 'Design & Creative' })).toBeChecked()
    expect(screen.getByLabelText('County')).toHaveValue('Nairobi')
    expect(screen.getByLabelText('Remote gigs only')).toBeChecked()
    expect(screen.getByLabelText('Minimum budget in KES')).toHaveValue(1000)
    expect(screen.getByLabelText('Show closed gigs')).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Last 30 days' })).toBeChecked()
  })

  it('calls onClear from "Clear all"', () => {
    const { onClear } = renderSidebar()
    fireEvent.click(screen.getByRole('button', { name: 'Clear all' }))
    expect(onClear).toHaveBeenCalledTimes(1)
  })

  it('groups the radio sets with a label for screen readers', () => {
    renderSidebar()
    expect(screen.getByRole('radiogroup', { name: 'Category' })).toBeInTheDocument()
    expect(screen.getByRole('radiogroup', { name: 'Posted within' })).toBeInTheDocument()
  })
})
