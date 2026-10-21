import { describe, expect, it } from 'vitest'
import { buildApplicationPayload, readApplicationError, validateApplication } from './applicationForm'

const LETTER = 'I have five years of experience building exactly this kind of thing for small businesses.'
const blank = { coverLetter: LETTER, portfolioLink: '', proposedRate: '' }

describe('validateApplication', () => {
  it('accepts a cover letter alone', () => {
    expect(validateApplication(blank)).toEqual({})
  })

  it('asks for a cover letter when it is empty or only spaces', () => {
    expect(validateApplication({ ...blank, coverLetter: '   ' }).cover_letter).toBe('Please write a cover letter.')
  })

  it('enforces the length limits on the trimmed letter', () => {
    expect(validateApplication({ ...blank, coverLetter: 'Too short' }).cover_letter).toMatch(/at least 50/)
    expect(validateApplication({ ...blank, coverLetter: 'x'.repeat(3001) }).cover_letter).toMatch(/at most 3000/)
    expect(validateApplication({ ...blank, coverLetter: 'x'.repeat(3000) })).toEqual({})
  })

  it('rejects a portfolio link that is not a web address', () => {
    expect(validateApplication({ ...blank, portfolioLink: 'my work' }).portfolio_link).toMatch(/full web address/)
    expect(validateApplication({ ...blank, portfolioLink: 'https://example.com/me' })).toEqual({})
  })

  it('rejects a rate of zero or less but allows leaving it blank', () => {
    expect(validateApplication({ ...blank, proposedRate: '0' }).proposed_rate).toMatch(/more than zero/)
    expect(validateApplication({ ...blank, proposedRate: '-5' }).proposed_rate).toMatch(/more than zero/)
    expect(validateApplication({ ...blank, proposedRate: '1500' })).toEqual({})
  })
})

describe('buildApplicationPayload', () => {
  it('leaves out optional fields that were left blank', () => {
    expect(buildApplicationPayload({ ...blank, coverLetter: `  ${LETTER}  ` })).toEqual({ cover_letter: LETTER })
  })

  it('includes the optional fields when filled', () => {
    expect(
      buildApplicationPayload({ coverLetter: LETTER, portfolioLink: ' https://example.com ', proposedRate: '1500' })
    ).toEqual({ cover_letter: LETTER, portfolio_link: 'https://example.com', proposed_rate: '1500' })
  })
})

describe('readApplicationError', () => {
  const errorWith = (data) => ({ response: { data } })

  it('maps field errors to their fields', () => {
    const result = readApplicationError(errorWith({ proposed_rate: ['The proposed rate must be more than zero.'] }))
    expect(result.fields.proposed_rate).toBe('The proposed rate must be more than zero.')
    expect(result.message).toBe('')
  })

  it('shows rule failures as a general message', () => {
    const result = readApplicationError(errorWith({ detail: 'You have already applied to this gig.' }))
    expect(result.message).toBe('You have already applied to this gig.')
    expect(result.fields).toEqual({})
  })

  it('falls back to a plain message when there is no response', () => {
    expect(readApplicationError(new Error('Network Error')).message).toBe('Something went wrong. Please try again.')
  })
})
