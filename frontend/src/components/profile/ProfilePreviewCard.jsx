import { BadgeCheck, MapPin } from 'lucide-react'
import { chipColour, initials, profileColour } from '../../utils/palette'

const PORTFOLIO_TILES = ['bg-coral-light text-coral-ink', 'bg-mint-light text-mint-ink', 'bg-ocean-light text-ocean-ink']

export function formatPrice(price) {
  return price ? `KES ${Number(price).toLocaleString('en-KE')}` : 'On request'
}

function memberSinceLabel(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
}

function Stat({ label, value, className, labelClass }) {
  return (
    <div className={`rounded-button p-3 flex flex-col gap-0.5 ${className}`}>
      <span className={`text-[12px] font-semibold ${labelClass}`}>{label}</span>
      <span className="font-display text-[17px] font-extrabold text-ink">{value}</span>
    </div>
  )
}

/**
 * A freelancer's profile as clients see it. The Edit profile page passes the unsaved draft, with
 * `placeholders` on so empty fields show what goes there; the public profile passes saved data and
 * leaves empty fields out. `strength` ({ value, tip }) is only shown on the Edit profile page.
 */
export default function ProfilePreviewCard({ profile, placeholders = false, strength = null }) {
  const colour = profileColour(profile.colour)
  const name = profile.name?.trim()
  const headline = profile.headline?.trim()
  const bio = profile.bio?.trim()
  const portfolio = profile.portfolioItems || []

  return (
    <article className="bg-surface rounded-preview overflow-hidden shadow-preview">
      <div className={`h-24 flex justify-end items-start p-3.5 ${colour.tint}`}>
        <span className={`text-badge px-[11px] py-[5px] rounded-pill bg-white ${profile.available ? 'text-accent' : 'text-ink-soft'}`}>
          {profile.available ? 'Available now' : 'Fully booked'}
        </span>
      </div>
      <div className="px-6 pb-6 flex flex-col gap-4">
        {profile.photoUrl ? (
          <img
            src={profile.photoUrl}
            alt=""
            className="-mt-10 w-20 h-20 rounded-full border-4 border-white object-cover"
          />
        ) : (
          <div
            aria-hidden="true"
            className={`-mt-10 w-20 h-20 rounded-full border-4 border-white flex items-center justify-center font-display font-extrabold text-[28px] ${colour.solid} ${colour.text}`}
          >
            {initials(name)}
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-[26px] font-extrabold tracking-[-0.02em] leading-tight">
              {name || (placeholders ? '[Your name]' : '')}
            </h2>
            {profile.verified && (
              <BadgeCheck size={22} className="text-white fill-primary" role="img" aria-label="Verified freelancer" />
            )}
          </div>
          {(headline || placeholders) && <p className="text-body text-ink-soft">{headline || '[Your headline]'}</p>}
          {(profile.county || placeholders) && (
            <span className="inline-flex items-center gap-1.5 text-[14px] text-muted">
              <MapPin size={15} aria-hidden="true" />
              {profile.county || '[Your county]'}
            </span>
          )}
        </div>

        <div className="grid grid-cols-3 gap-2">
          <Stat label="From" value={formatPrice(profile.price)} className="bg-sun-light" labelClass="text-sun-deep" />
          <Stat label="Gigs done" value={profile.gigsCompleted ?? 0} className="bg-ocean-light" labelClass="text-ocean-ink" />
          <Stat
            label="Member since"
            value={memberSinceLabel(profile.memberSince) || '-'}
            className="bg-plum-light"
            labelClass="text-plum-ink"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-[14px] font-bold">About</h3>
          <p className="text-[15px] leading-[1.55] text-prose whitespace-pre-line">
            {bio || (placeholders ? 'Tell clients what you do and who you have worked with.' : 'No bio yet.')}
          </p>
        </div>

        <div className="flex flex-col gap-2">
          <h3 className="text-[14px] font-bold">Skills</h3>
          {profile.skills.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {profile.skills.map((skill, i) => (
                <span key={skill.id || skill.name} className={`text-caption font-semibold px-3 py-[5px] rounded-pill ${chipColour(i)}`}>
                  {skill.name}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-caption text-muted">No skills listed yet.</p>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <h3 className="text-[14px] font-bold">Portfolio</h3>
          {portfolio.length > 0 ? (
            <div className="grid grid-cols-3 gap-2">
              {portfolio.slice(0, 3).map((item, i) => (
                <div
                  key={item.id}
                  className={`relative aspect-square rounded-button p-2.5 flex items-end text-[12px] font-bold overflow-hidden ${PORTFOLIO_TILES[i]}`}
                >
                  {item.image && <img src={item.image} alt="" className="absolute inset-0 w-full h-full object-cover" />}
                  <span className={`relative line-clamp-2 ${item.image ? 'bg-white/90 rounded-md px-1.5 py-0.5' : ''}`}>
                    {item.title}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-caption text-muted">No portfolio items yet.</p>
          )}
        </div>

        {strength && (
          <div className="flex flex-col gap-1.5 pt-3.5 border-t border-dashed border-divider">
            <div className="flex justify-between text-caption font-semibold">
              <span>Profile strength</span>
              <span className="text-primary">{strength.value}%</span>
            </div>
            <div
              role="progressbar"
              aria-valuenow={strength.value}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Profile strength"
              className="h-2 rounded-pill bg-track overflow-hidden"
            >
              <div className="h-full bg-primary rounded-pill transition-[width]" style={{ width: `${strength.value}%` }} />
            </div>
            <span className="text-caption text-muted">{strength.tip}</span>
          </div>
        )}
      </div>
    </article>
  )
}
