import { Link, useLocation } from 'react-router-dom'
import { logRecommendationClick } from '../../api/gigs'
import { formatBudget } from '../../utils/gigFormat'
import { categoryColour } from '../../utils/palette'
import RelevanceQuestion from './RelevanceQuestion'

// One recommended gig on the teal "Picked for you" band.
export default function PickCard({ gig, position }) {
  const location = useLocation()

  return (
    <article className="flex flex-col gap-3 p-[18px] rounded-tile bg-surface text-ink">
      <span
        className={`self-start text-badge px-2.5 py-1 rounded-pill ${categoryColour(gig.category.slug || gig.category.name)}`}
      >
        {gig.category.name}
      </span>
      <h3 className="font-display text-lead font-bold leading-[1.25]">
        <Link
          to={`/gigs/${gig.id}`}
          state={{ from: `${location.pathname}${location.search}` }}
          onClick={() => logRecommendationClick(gig.id, position)}
          className="text-ink hover:text-primary"
        >
          {gig.title}
        </Link>
      </h3>
      {gig.match_reasons.length > 0 && (
        <p className="text-caption text-muted">Matches your skills: {gig.match_reasons.join(', ')}</p>
      )}
      <span className="self-start text-[15px] font-bold bg-sun-light text-sun-deep px-3 py-[5px] rounded-pill">
        {formatBudget(gig)}
      </span>
      <div className="mt-auto pt-3 border-t border-dashed border-divider">
        <RelevanceQuestion gigId={gig.id} gigTitle={gig.title} position={position} initial={gig.relevance} />
      </div>
    </article>
  )
}
