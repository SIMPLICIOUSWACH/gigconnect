import { BadgeCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchPublicProfile } from '../api/profile'
import { industryLabel } from '../constants'
import { useAuth } from '../context/AuthContext'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card from '../components/Card'

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
        <div key={item.id} className="border border-border rounded-xl overflow-hidden bg-surface">
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
  return (
    <>
      <Card variant="elevated" className="mb-6">
        <div className="flex items-center gap-6">
          <Avatar src={p.profile_photo} name={profile.full_name} />
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-section-title text-ink">{profile.full_name}</h2>
              {p.verified && (
                <span className="inline-flex items-center gap-1 text-caption font-medium text-accent bg-accent-light px-2 py-1 rounded-full">
                  <BadgeCheck size={14} /> Verified
                </span>
              )}
            </div>
          </div>
        </div>
        <p className="text-body text-ink mt-6">
          {p.bio || <span className="text-muted">No bio yet.</span>}
        </p>
      </Card>

      <Card className="mb-6">
        <h2 className="text-section-title text-ink mb-4">Skills</h2>
        {p.skills?.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {p.skills.map((skill) => (
              <span
                key={skill.id}
                className="text-caption font-medium px-3 py-1.5 rounded-full bg-primary-light text-primary"
              >
                {skill.name}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-body text-muted">No skills listed.</p>
        )}
      </Card>

      <Card className="mb-6">
        <h2 className="text-section-title text-ink mb-4">Portfolio</h2>
        <PortfolioGrid items={p.portfolio_items} />
      </Card>

      <Card>
        <h2 className="text-section-title text-ink mb-2">Ratings & Gig Stats</h2>
        <p className="text-body text-muted">
          Ratings and completed-gig stats will show here once Application Tracking (Sprint 4) and the
          ML Recommendation Engine (Sprint 5) are built — there's no data to show yet.
        </p>
      </Card>
    </>
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

      <Card>
        <h2 className="text-section-title text-ink mb-2">Posted Gigs</h2>
        <p className="text-body text-muted">
          This will list {p.company_name || profile.full_name}'s active gig postings once Gig Posting
          (Sprint 2) is built — there's no gig data yet.
        </p>
      </Card>
    </>
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
  const editPath = profile?.role === 'client' ? '/settings/company-profile' : '/settings/freelancer-profile'

  return (
    <div className="max-w-[960px]">
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
