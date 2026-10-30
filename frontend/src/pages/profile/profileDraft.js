// The Edit profile page keeps two copies of the profile: the saved one and the draft being edited.
// These helpers build, compare and score them, following design_reference/profile_edit.html.

export const BIO_MAX = 300
export const BIO_MIN_FOR_STRENGTH = 60
export const SKILLS_FOR_STRENGTH = 3

export function draftFromUser(user) {
  const p = user?.profile || {}
  return {
    name: user?.full_name || '',
    headline: p.headline || '',
    county: p.county || '',
    bio: p.bio || '',
    price: p.starting_price ? String(p.starting_price) : '',
    skills: (p.skills || []).map((s) => ({ id: s.id, name: s.name })),
    colour: p.profile_colour || 'teal',
    available: p.is_available ?? true,
  }
}

export function isDirty(draft, saved) {
  return JSON.stringify(draft) !== JSON.stringify(saved)
}

// Digits only, as the mockup's price field does.
export function cleanPrice(value) {
  return String(value).replace(/[^0-9]/g, '')
}

// Six checks, each worth a sixth, and the tip for the first one still missing.
export function profileStrength(draft) {
  const bioLength = draft.bio.trim().length
  const price = Number(draft.price || 0)
  const checks = [
    Boolean(draft.name.trim()),
    Boolean(draft.headline.trim()),
    Boolean(draft.county),
    bioLength >= BIO_MIN_FOR_STRENGTH,
    draft.skills.length >= SKILLS_FOR_STRENGTH,
    price > 0,
  ]
  const value = Math.round((checks.filter(Boolean).length / checks.length) * 100)
  let tip = 'Looking good. Add a portfolio item next.'
  if (bioLength < BIO_MIN_FOR_STRENGTH) tip = `Write a bio of at least ${BIO_MIN_FOR_STRENGTH} characters.`
  else if (draft.skills.length < SKILLS_FOR_STRENGTH) tip = `Add at least ${SKILLS_FOR_STRENGTH} skills for better matches.`
  else if (!price) tip = 'Set a starting price.'
  return { value, tip }
}

// Adds a skill to the draft unless it is already there (by id, or by name ignoring case).
export function withSkill(skills, skill) {
  const exists = skills.some((s) => s.id === skill.id || s.name.toLowerCase() === skill.name.toLowerCase())
  return exists ? skills : [...skills, { id: skill.id, name: skill.name }]
}
