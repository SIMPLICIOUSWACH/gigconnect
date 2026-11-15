import { useRef, useState } from 'react'
import { Star } from 'lucide-react'

const VALUES = [1, 2, 3, 4, 5]
export const starLabel = (value) => `${value} ${value === 1 ? 'star' : 'stars'}`

/*
  A 1 to 5 star rating as a radio group. With the keyboard: Tab reaches the group, the arrow keys move and choose
  (Home and End jump to 1 and 5), and Space or Enter choose the focused star. Each star is announced as "1 star",
  "2 stars" and so on. `value` is 0 while nothing is chosen.
*/
export default function StarInput({ value, onChange, label = 'Rating', disabled = false }) {
  const [hovered, setHovered] = useState(0)
  const stars = useRef([])
  const shown = hovered || value
  // One tab stop for the whole group: the chosen star, or the first one while nothing is chosen.
  const tabStop = value || 1

  const choose = (next) => {
    onChange(next)
    stars.current[next - 1]?.focus()
  }

  const onKeyDown = (e, star) => {
    let next = null
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp') next = Math.min(5, (value || star - 1) + 1)
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') next = Math.max(1, (value || star + 1) - 1)
    else if (e.key === 'Home') next = 1
    else if (e.key === 'End') next = 5
    else if (e.key === ' ' || e.key === 'Enter') next = star
    if (next === null) return
    e.preventDefault()
    choose(next)
  }

  return (
    <div role="radiogroup" aria-label={label} className="inline-flex gap-1" onMouseLeave={() => setHovered(0)}>
      {VALUES.map((star) => (
        <button
          key={star}
          ref={(node) => {
            stars.current[star - 1] = node
          }}
          type="button"
          role="radio"
          aria-checked={value === star}
          aria-label={starLabel(star)}
          tabIndex={star === tabStop ? 0 : -1}
          disabled={disabled}
          onClick={() => choose(star)}
          onKeyDown={(e) => onKeyDown(e, star)}
          onMouseEnter={() => setHovered(star)}
          className="w-11 h-11 rounded-input flex items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed"
        >
          <Star
            size={30}
            aria-hidden="true"
            className={star <= shown ? 'fill-sun text-sun' : 'fill-transparent text-toggle-off'}
          />
        </button>
      ))}
    </div>
  )
}
