import { describe, expect, it } from 'vitest'
import { formatBudget, isApplicationClosed, isUrgent } from './gigFormat'

describe('formatBudget', () => {
  it('shows a range when min and max differ', () => {
    expect(formatBudget({ currency: 'KES', budget_min: '15000', budget_max: '25000' })).toBe(
      'KES 15,000 – 25,000'
    )
  })

  it('shows a single value when min equals max', () => {
    expect(formatBudget({ currency: 'KES', budget_min: '20000', budget_max: '20000' })).toBe('KES 20,000')
  })
})

describe('isUrgent', () => {
  it('is false when there is no application deadline', () => {
    expect(isUrgent(null)).toBe(false)
  })

  it('is false when the deadline is more than 3 days away', () => {
    const future = new Date()
    future.setDate(future.getDate() + 10)
    expect(isUrgent(future.toISOString().slice(0, 10))).toBe(false)
  })

  it('is true when the deadline is within the next 3 days', () => {
    const soon = new Date()
    soon.setDate(soon.getDate() + 2)
    expect(isUrgent(soon.toISOString().slice(0, 10))).toBe(true)
  })

  it('is false once the deadline has already passed', () => {
    const past = new Date()
    past.setDate(past.getDate() - 1)
    expect(isUrgent(past.toISOString().slice(0, 10))).toBe(false)
  })
})

describe('isApplicationClosed', () => {
  it('is false when there is no application deadline', () => {
    expect(isApplicationClosed(null)).toBe(false)
  })

  it('is false for a future deadline', () => {
    const future = new Date()
    future.setDate(future.getDate() + 1)
    expect(isApplicationClosed(future.toISOString().slice(0, 10))).toBe(false)
  })

  it('is true for a past deadline', () => {
    const past = new Date()
    past.setDate(past.getDate() - 1)
    expect(isApplicationClosed(past.toISOString().slice(0, 10))).toBe(true)
  })
})
