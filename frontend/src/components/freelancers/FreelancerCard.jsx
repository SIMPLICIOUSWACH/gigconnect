import { BadgeCheck, Briefcase, MapPin, Wifi } from 'lucide-react'
import { Link } from 'react-router-dom'
import { chipColour, initials, profileColour } from '../../utils/palette'
import { formatPrice } from '../profile/ProfilePreviewCard'
import RatingSummary from '../reviews/RatingSummary'

const BAND_LABELS = {
  strong: 'Strong skill overlap',
  good: 'Good skill overlap',
  some: 'Some skill overlap',
}

export function Avatar({ freelancer, size = 'w-14 h-14 text-[18px]' }) {
  const colour = profileColour(freelancer.profile_colour)
  if (freelancer.profile_photo) {
    return <img src={freelancer.profile_photo} alt="" className={`${size} rounded-full object-cover shrink-0`} />
  }
  return (
    <span
      aria-hidden="true"
      className={`${size} shrink-0 rounded-full flex items-center justify-center font-bold ${colour.solid} ${colour.text}`}
    >
      {initials(freelancer.full_name)}
    </span>
  )
}

/*
  A freelancer as a client sees them in Find freelancers and in "Suggested for this gig". When the card carries a
  match (suggestions do), it shows the same skill-overlap label and shared skills as an applicant card. `action` is
  the invite button, which the page supplies.
*/
export default function FreelancerCard({ freelancer, action }) {
  const more = freelancer.skills_total - freelancer.skills.length
  const completed = freelancer.gigs_completed
  return (
    <article className="bg-surface rounded-card shadow-hairline hover:shadow-raised transition-shadow p-5 flex flex-col gap-3 h-full">
      <div className="flex items-start gap-3">
        <Avatar freelancer={freelancer} />
        <div className="min-w-0 flex-1">
          <h3 className="flex items-center gap-1.5 text-[17px] leading-6 font-bold text-ink">
            <span className="truncate">{freelancer.full_name}</span>
            {freelancer.verified && (
              <BadgeCheck
                size={18}
                className="text-white fill-primary shrink-0"
                role="img"
                aria-label="Verified freelancer"
              />
            )}
          </h3>
          {freelancer.headline && <p className="text-[14px] leading-5 text-ink-soft line-clamp-2">{freelancer.headline}</p>}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <RatingSummary average={freelancer.rating_avg} count={freelancer.rating_count} />
        <span className="inline-flex items-center gap-1 text-[13px] text-muted">
          <Briefcase size={14} aria-hidden="true" />
          {completed} {completed === 1 ? 'gig' : 'gigs'} completed
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-muted">
        {freelancer.county && (
          <span className="inline-flex items-center gap-1">
            <MapPin size={14} aria-hidden="true" />
            {freelancer.county}
          </span>
        )}
        {freelancer.open_to_remote && (
          <span className="inline-flex items-center gap-1">
            <Wifi size={14} aria-hidden="true" />
            Open to remote
          </span>
        )}
      </div>

      {freelancer.skills.length > 0 && (
        <ul aria-label="Top skills" className="flex flex-wrap gap-1.5">
          {freelancer.skills.map((skill, index) => (
            <li key={skill.id} className={`text-[12px] font-semibold px-2.5 py-1 rounded-pill ${chipColour(index)}`}>
              {skill.name}
            </li>
          ))}
          {more > 0 && <li className="text-[12px] font-semibold px-2.5 py-1 rounded-pill bg-sand text-ink-soft">+{more} more</li>}
        </ul>
      )}

      {freelancer.match_band && (
        <p className="text-caption text-muted border border-border rounded-lg px-3 py-2">
          <span className="font-medium text-ink">{BAND_LABELS[freelancer.match_band]}</span>
          {freelancer.match_reasons?.length > 0 && <> · Shared skills: {freelancer.match_reasons.join(', ')}</>}
        </p>
      )}

      <div className="mt-auto pt-3 border-t border-line flex flex-wrap items-center justify-between gap-3">
        <div className="text-[13px] leading-5">
          <p className="font-bold text-ink">
            {freelancer.starting_price ? `From ${formatPrice(freelancer.starting_price)}` : 'Price on request'}
          </p>
          <p className={freelancer.is_available ? 'text-accent font-semibold' : 'text-muted'}>
            {freelancer.is_available ? 'Available now' : 'Not available now'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/profile/${freelancer.id}`}
            className="inline-flex items-center min-h-[40px] px-3 rounded-button text-[14px] font-bold text-primary hover:bg-sand"
          >
            View profile
            <span className="sr-only"> of {freelancer.full_name}</span>
          </Link>
          {action}
        </div>
      </div>
    </article>
  )
}
