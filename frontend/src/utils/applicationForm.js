export const COVER_LETTER_MIN = 50
export const COVER_LETTER_MAX = 3000

const FIELDS = ['cover_letter', 'portfolio_link', 'proposed_rate']
const FALLBACK = 'Something went wrong. Please try again.'

/** Checks the form before it is sent. The server repeats these checks; this just saves a round trip. */
export function validateApplication({ coverLetter, portfolioLink, proposedRate }) {
  const errors = {}
  const letter = coverLetter.trim()
  if (!letter) errors.cover_letter = 'Please write a cover letter.'
  else if (letter.length < COVER_LETTER_MIN)
    errors.cover_letter = `Your cover letter needs at least ${COVER_LETTER_MIN} characters.`
  else if (letter.length > COVER_LETTER_MAX)
    errors.cover_letter = `Your cover letter can be at most ${COVER_LETTER_MAX} characters.`

  const link = portfolioLink.trim()
  if (link && !/^https?:\/\/\S+\.\S+/.test(link))
    errors.portfolio_link = 'Enter a full web address, for example https://example.com.'

  const rate = proposedRate.trim()
  if (rate && !(Number(rate) > 0)) errors.proposed_rate = 'The proposed rate must be more than zero.'

  return errors
}

/** Builds the request body, leaving out the optional fields that were left blank. */
export function buildApplicationPayload({ coverLetter, portfolioLink, proposedRate }) {
  const payload = { cover_letter: coverLetter.trim() }
  if (portfolioLink.trim()) payload.portfolio_link = portfolioLink.trim()
  if (proposedRate.trim()) payload.proposed_rate = proposedRate.trim()
  return payload
}

/**
 * Turns an API error into { fields, message }: field problems to show under the inputs, and a
 * general message for everything else (rule failures, permission problems, network errors).
 */
export function readApplicationError(err) {
  const data = err?.response?.data
  if (!data || typeof data !== 'object') return { fields: {}, message: FALLBACK }

  const fields = {}
  for (const name of FIELDS) {
    const value = data[name]
    if (value) fields[name] = Array.isArray(value) ? value[0] : String(value)
  }
  if (Object.keys(fields).length > 0) return { fields, message: '' }
  return { fields: {}, message: typeof data.detail === 'string' ? data.detail : FALLBACK }
}
