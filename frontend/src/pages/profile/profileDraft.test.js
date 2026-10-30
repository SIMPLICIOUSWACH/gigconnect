import { describe, expect, it } from 'vitest'
import { cleanPrice, draftFromUser, isDirty, profileStrength, withSkill } from './profileDraft'

const full = {
  name: 'Amina Wanjiru',
  headline: 'Copywriter',
  county: 'Nairobi',
  bio: 'I write product pages and newsletters for small shops in Nairobi and Mombasa.',
  price: '5000',
  skills: [
    { id: 'a', name: 'Copywriting' },
    { id: 'b', name: 'Canva' },
    { id: 'c', name: 'SEO' },
  ],
  colour: 'teal',
  available: true,
}

describe('draftFromUser', () => {
  it('reads the saved profile, with defaults for a new freelancer', () => {
    expect(draftFromUser({ full_name: 'Amina', profile: {} })).toEqual({
      name: 'Amina',
      headline: '',
      county: '',
      bio: '',
      price: '',
      skills: [],
      colour: 'teal',
      available: true,
    })
  })

  it('keeps an explicit "not available" and the price as text', () => {
    const draft = draftFromUser({ full_name: 'A', profile: { is_available: false, starting_price: 7500 } })
    expect(draft.available).toBe(false)
    expect(draft.price).toBe('7500')
  })
})

describe('isDirty', () => {
  it('is false for an identical copy and true after any change', () => {
    expect(isDirty({ ...full }, full)).toBe(false)
    expect(isDirty({ ...full, headline: 'Writer' }, full)).toBe(true)
    expect(isDirty({ ...full, skills: full.skills.slice(1) }, full)).toBe(true)
  })
})

describe('profileStrength', () => {
  it('is 100 when all six checks pass', () => {
    expect(profileStrength(full)).toEqual({ value: 100, tip: 'Looking good. Add a portfolio item next.' })
  })

  it('scores each missing check as a sixth and gives the first tip that applies', () => {
    expect(profileStrength({ ...full, bio: 'Short bio' })).toEqual({
      value: 83,
      tip: 'Write a bio of at least 60 characters.',
    })
    expect(profileStrength({ ...full, skills: full.skills.slice(0, 2) }).tip).toBe(
      'Add at least 3 skills for better matches.'
    )
    expect(profileStrength({ ...full, price: '' })).toEqual({ value: 83, tip: 'Set a starting price.' })
    expect(profileStrength({ ...full, name: ' ', headline: '', county: '' }).value).toBe(50)
  })
})

describe('helpers', () => {
  it('cleanPrice keeps digits only', () => {
    expect(cleanPrice('KES 5,000')).toBe('5000')
  })

  it('withSkill ignores a skill already there by id or by name in any case', () => {
    expect(withSkill(full.skills, { id: 'a', name: 'Copywriting' })).toBe(full.skills)
    expect(withSkill(full.skills, { id: 'z', name: 'canva' })).toBe(full.skills)
    expect(withSkill(full.skills, { id: 'd', name: 'Excel' })).toHaveLength(4)
  })
})
