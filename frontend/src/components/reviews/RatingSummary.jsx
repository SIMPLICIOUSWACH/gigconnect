import { Star } from 'lucide-react'

// "4.6" from the stored average ("4.60"), or '' when there are no reviews.
export function ratingNumber(average) {
  return average === null || average === undefined || average === '' ? '' : Number(average).toFixed(1)
}

/*
  A freelancer's rating in one line: "★ 4.6 · 12 reviews". Someone with no reviews is "New", never 0 stars.
*/
export default function RatingSummary({ average, count = 0, className = '' }) {
  if (!count || ratingNumber(average) === '') {
    return (
      <span className={`inline-flex items-center text-badge px-2.5 py-1 rounded-pill bg-mint-light text-mint-ink ${className}`}>
        New
      </span>
    )
  }
  const reviews = `${count} ${count === 1 ? 'review' : 'reviews'}`
  return (
    <span className={`inline-flex items-center gap-1 text-[14px] leading-5 text-ink ${className}`}>
      <Star size={15} aria-hidden="true" className="fill-sun text-sun" />
      <span className="font-bold">{ratingNumber(average)}</span>
      <span className="sr-only">out of 5,</span>
      <span className="text-muted">· {reviews}</span>
    </span>
  )
}
