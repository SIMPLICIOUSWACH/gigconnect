// Direction B colour helpers. Every class is written out in full so Tailwind keeps it in the build.

// A freelancer's profile colour: the avatar (solid + text) and the profile header (tint).
export const PROFILE_COLOURS = {
  teal: { label: 'Teal', solid: 'bg-primary', text: 'text-white', tint: 'bg-primary-light' },
  coral: { label: 'Coral', solid: 'bg-coral', text: 'text-ink', tint: 'bg-coral-light' },
  sun: { label: 'Sunflower', solid: 'bg-sun', text: 'text-ink', tint: 'bg-sun-light' },
  violet: { label: 'Violet', solid: 'bg-plum', text: 'text-white', tint: 'bg-plum-light' },
  rose: { label: 'Rose', solid: 'bg-berry', text: 'text-white', tint: 'bg-berry-light' },
}

export function profileColour(key) {
  return PROFILE_COLOURS[key] || PROFILE_COLOURS.teal
}

// Light background + readable text pairs, for categories and skill chips.
export const CHIP_COLOURS = [
  'bg-mint-light text-mint-ink',
  'bg-coral-light text-coral-ink',
  'bg-plum-light text-plum-ink',
  'bg-ocean-light text-ocean-ink',
  'bg-sun-light text-sun-ink',
  'bg-berry-light text-berry-ink',
]

export function chipColour(index) {
  return CHIP_COLOURS[index % CHIP_COLOURS.length]
}

const CATEGORY_COLOURS = {
  'design-creative': 'bg-coral-light text-coral-ink',
  'marketing-sales': 'bg-sun-light text-sun-ink',
  'web-software-development': 'bg-ocean-light text-ocean-ink',
  'writing-content': 'bg-plum-light text-plum-ink',
  'admin-virtual-assistance': 'bg-mint-light text-mint-ink',
  'local-services': 'bg-berry-light text-berry-ink',
  'data-analytics': 'bg-ocean-light text-ocean-ink',
  'video-photography': 'bg-coral-light text-coral-ink',
}

// The same category always gets the same colour, wherever it appears. Categories added later get
// one from their slug.
export function categoryColour(slug = '') {
  if (CATEGORY_COLOURS[slug]) return CATEGORY_COLOURS[slug]
  let hash = 0
  for (const ch of slug) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return chipColour(hash)
}

// Up to two initials from a name, or "?" when there is none.
export function initials(name = '') {
  const letters = name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join('')
  return letters || '?'
}
