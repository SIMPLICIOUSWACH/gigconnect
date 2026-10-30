import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchGigsPaged } from '../api/gigs'
import { fetchPublicProfile } from '../api/profile'
import { industryLabel } from '../constants'
import { useAuth } from '../context/AuthContext'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card from '../components/Card'
import GigCard from '../components/gigs/GigCard'
import GigCardSkeleton from '../components/gigs/GigCardSkeleton'
import ProfilePreviewCard from '../components/profile/ProfilePreviewCard'

function Avatar({ src, name }) {
  if (src) {
    return <img src={src} alt={name} className="w-20 h-20 rounded-full object-cover border border-border" />
  }
  return (
    <div className="w-20 h-20 rounded-full bg-primary-light flex items-center justify-center text-primary text-page-title shrink-0">
      {name?.[0]?.toUpperCase() || '?'}
    </div>
  )
}

function PortfolioGrid({ items }) {
  if (!items || items.length === 0) {
    return <p className="text-body text-muted">No portfolio items yet.</p>
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
      {items.map((item) => (
        <div key={item.id} className="border border-line rounded-tile overflow-hidden bg-surface">
          {item.image ? (
            <img src={item.image} alt={item.title} className="w-full h-40 object-cover" />
          ) : (
            <div className="w-full h-40 bg-bg flex items-center justify-center text-muted text-caption">
              No image
            </div>
          )}
          <div className="p-5">
            <h3 className="text-section-title text-ink mb-1">{item.title}</h3>
            {item.description && <p className="text-body text-muted mb-3">{item.description}</p>}
            {item.link && (
              <a
                href={item.link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-body text-primary font-medium"
              >
                View project
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function FreelancerView({ profile }) {
  const p = profile.profile || {}
  const card = {
    name: profile.full_name,
    headline: p.headline,
    county: p.county,
    bio: p.bio,
    price: p.starting_price,
    skills: p.skills || [],
    colour: p.profile_colour,
    available: p.is_available ?? true,
    photoUrl: p.profile_photo,
    verified: p.verified,
    gigsCompleted: p.gigs_completed,
    memberSince: p.member_since,
    portfolioItems: p.portfolio_items,
  }
  return (
    <div className="flex flex-wrap gap-7 items-start">
      <div className="flex-[1_1_380px] max-w-[460px] min-w-0">
        <ProfilePreviewCard profile={card} />
      </div>
      <Card className="flex-[999_1_420px] min-w-0">
        <h2 className="text-section-title text-ink mb-4">Portfolio</h2>
        <PortfolioGrid items={p.portfolio_items} />
      </Card>
    </div>
  )
}

function ClientView({ profile }) {
  const p = profile.profile || {}
  return (
    <>
      <Card variant="elevated" className="mb-6">
        <div className="flex items-center gap-6">
          <Avatar src={p.company_logo} name={p.company_name || profile.full_name} />
          <div>
            <h2 className="text-section-title text-ink">{p.company_name || profile.full_name}</h2>
            {p.industry && <p className="text-body text-muted mt-1">{industryLabel(p.industry)}</p>}
          </div>
        </div>
      </Card>

      <ClientGigs clientId={profile.id} name={p.company_name || profile.full_name} />
    </>
  )
}

const CLIENT_GIGS_PAGE_SIZE = 12

// The client's gigs that are open to applications right now: the same rules as the Browse gigs feed.
function ClientGigs({ clientId, name }) {
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    setResult(null)
    setError('')
    fetchGigsPaged({ client: clientId, page_size: CLIENT_GIGS_PAGE_SIZE })
      .then((data) => alive && setResult(data))
      .catch(() => alive && setError('Could not load these gigs.'))
    return () => {
      alive = false
    }
  }, [clientId])

  return (
    <section aria-labelledby="client-gigs-heading">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
        <h2 id="client-gigs-heading" className="text-section-heading text-ink">
          Open gigs
        </h2>
        {result && result.count > result.results.length && (
          <p className="text-caption text-muted">
            Showing the newest {result.results.length} of {result.count}
          </p>
        )}
      </div>

      {error && <Alert type="error">{error}</Alert>}

      {!result && !error && (
        <div aria-label="Loading gigs" className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <GigCardSkeleton key={i} />
          ))}
        </div>
      )}

      {result?.results.length === 0 && (
        <Card>
          <p className="text-body text-muted">{name} has no gigs open for applications right now.</p>
        </Card>
      )}

      {result?.results.length > 0 && (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {result.results.map((gig, index) => (
            // A profile is not a search, so opening a gig from here is not logged as a search click.
            <GigCard key={gig.id} gig={gig} position={index + 1} onOpen={() => {}} />
          ))}
        </div>
      )}
    </section>
  )
}

export default function PublicProfile() {
  const { id } = useParams()
  const { user } = useAuth()
  const [profile, setProfile] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setProfile(null)
    setError('')
    fetchPublicProfile(id)
      .then(setProfile)
      .catch(() => setError('Could not load this profile.'))
  }, [id])

  const isOwnProfile = user?.id === id
  const editPath = profile?.role === 'client' ? '/settings/company-profile' : '/profile/edit'

  return (
    <div className="max-w-[1000px]">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-page-title text-primary">Profile</h1>
        {isOwnProfile && (
          <Link to={editPath}>
            <Button variant="secondary">Edit profile</Button>
          </Link>
        )}
      </div>

      {error && <Alert type="error">{error}</Alert>}
      {!profile && !error && <p className="text-body text-muted">Loading…</p>}
      {profile && (profile.role === 'freelancer' ? <FreelancerView profile={profile} /> : <ClientView profile={profile} />)}
    </div>
  )
}
