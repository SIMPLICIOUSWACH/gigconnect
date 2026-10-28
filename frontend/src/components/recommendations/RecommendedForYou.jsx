import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchRecommendations } from '../../api/recommendations'
import { logRecommendationClick } from '../../api/gigs'
import Alert from '../Alert'
import GigCard from '../gigs/GigCard'
import GigCardSkeleton from '../gigs/GigCardSkeleton'
import PickCard from './PickCard'
import RelevanceQuestion from './RelevanceQuestion'

const EDIT_SKILLS_PATH = '/profile/edit'

// What to say when there is nothing to show. The API gives a reason; no state ever shows a guess.
const EMPTY_MESSAGES = {
  disabled: 'Recommendations are switched off for now. Use search and filters to find gigs that match your skills.',
  model_unavailable:
    'Recommendations are not ready yet. They appear once the recommender has been trained. ' +
    'Use search and filters to find gigs that match your skills.',
}
const NO_CANDIDATES_MESSAGE =
  'There are no gigs to recommend right now. New gigs that match your skills will show up here.'

// variant "band" is the teal "Picked for you" band on Browse gigs; "list" is the plain section on the dashboard.
export default function RecommendedForYou({ limit = 6, heading = 'Recommended for You', subheading, variant = 'list' }) {
  const [state, setState] = useState({ status: 'loading' })
  const [retryTick, setRetryTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })
    fetchRecommendations({ page_size: limit })
      .then((data) => {
        if (!cancelled) setState({ status: 'done', data })
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'error' })
      })
    return () => {
      cancelled = true
    }
  }, [limit, retryTick])

  const body = <Body state={state} limit={limit} band={variant === 'band'} onRetry={() => setRetryTick((n) => n + 1)} />

  if (variant === 'band') {
    return (
      <section aria-labelledby="recommended-heading" className="bg-primary text-white">
        <div className="max-w-page mx-auto px-4 sm:px-8 py-9 flex flex-col gap-[18px]">
          <div className="flex flex-col gap-1">
            <h2 id="recommended-heading" className="text-band-title">
              {heading}
            </h2>
            {subheading && <p className="text-[15px] text-primary-soft">{subheading}</p>}
          </div>
          {body}
        </div>
      </section>
    )
  }

  return (
    <section aria-labelledby="recommended-heading" className="mt-12 pt-8 border-t border-line">
      <h2 id="recommended-heading" className="text-section-heading text-ink mb-3">
        {heading}
      </h2>
      {body}
    </section>
  )
}

function Body({ state, limit, band, onRetry }) {
  const note = band ? 'text-body text-primary-soft' : 'text-body text-muted'
  const link = band ? 'text-white font-semibold underline' : 'text-primary font-medium'

  if (state.status === 'loading') {
    return (
      <div
        className={band ? 'grid gap-3.5 grid-cols-[repeat(auto-fit,minmax(240px,1fr))]' : 'grid grid-cols-1 sm:grid-cols-2 gap-4'}
        aria-busy="true"
        aria-label="Loading recommendations"
      >
        {Array.from({ length: Math.min(limit, band ? 3 : 4) }).map((_, i) =>
          band ? <div key={i} className="h-[220px] rounded-tile bg-white/10 animate-pulse" /> : <GigCardSkeleton key={i} />
        )}
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <Alert type="error">
        Could not load your recommendations.{' '}
        <button type="button" onClick={onRetry} className="underline font-medium">
          Retry
        </button>
      </Alert>
    )
  }

  const { data } = state
  if (!data.available) {
    return <p className={note}>{EMPTY_MESSAGES[data.reason] ?? EMPTY_MESSAGES.model_unavailable}</p>
  }

  if (data.reason === 'no_skills') {
    return (
      <p className={note}>
        Add skills to your profile to get recommendations.{' '}
        <Link to={EDIT_SKILLS_PATH} className={link}>
          Edit your skills
        </Link>
      </p>
    )
  }

  if (data.results.length === 0) {
    return <p className={note}>{NO_CANDIDATES_MESSAGE}</p>
  }

  return (
    <>
      {data.cold_start && (
        <p className={`${note} mb-4`}>
          These are based on your skills, and they will improve as you apply to gigs.{' '}
          <Link to={EDIT_SKILLS_PATH} className={link}>
            Edit your skills
          </Link>
        </p>
      )}
      {band ? (
        <div className="grid gap-3.5 grid-cols-[repeat(auto-fit,minmax(240px,1fr))]">
          {data.results.map((gig, index) => (
            <PickCard key={gig.id} gig={gig} position={index + 1} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {data.results.map((gig, index) => (
            <div key={gig.id} className="flex flex-col gap-2">
              <GigCard gig={gig} position={index + 1} onOpen={(g, position) => logRecommendationClick(g.id, position)} />
              {gig.match_reasons.length > 0 && (
                <p className="text-caption text-muted px-1">Matches your skills: {gig.match_reasons.join(', ')}</p>
              )}
              <RelevanceQuestion gigId={gig.id} gigTitle={gig.title} position={index + 1} initial={gig.relevance} />
            </div>
          ))}
        </div>
      )}
    </>
  )
}
