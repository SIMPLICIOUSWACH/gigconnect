import { Search } from 'lucide-react'
import { formatBudget } from '../../utils/gigFormat'
import { categoryColour } from '../../utils/palette'

function gigsLabel(count) {
  return `${count} new gig${count === 1 ? '' : 's'} posted today`
}

// The decorative cards beside the heading, filled from real data: the newest open gig and the
// category with the most open gigs. Hidden from screen readers; the same facts are on the page.
function HeroCards({ newestGig, topCategory }) {
  if (!newestGig && !topCategory) return null

  return (
    <div aria-hidden="true" className="hidden md:block flex-[1_1_340px] relative h-[320px] min-w-0">
      {newestGig && (
        <div className="absolute top-0 right-[30px] w-[250px] bg-primary text-white rounded-card p-5 flex flex-col gap-2.5 rotate-3">
          <span className="text-caption font-semibold text-primary-soft">{newestGig.category.name}</span>
          <span className="font-display text-section-title leading-[1.2] line-clamp-3">{newestGig.title}</span>
          <span className="self-start text-[15px] font-bold bg-sun text-ink px-3 py-[5px] rounded-pill">
            {formatBudget(newestGig)}
          </span>
        </div>
      )}
      {newestGig && (
        <div className="absolute top-[130px] left-0 w-[230px] bg-surface rounded-card p-[18px] flex flex-col gap-1.5 shadow-float -rotate-[4deg]">
          <span className="text-[14px] font-semibold">Newest gig</span>
          <span className="text-[14px] text-ink-soft">
            Posted by {newestGig.client_name}
            {newestGig.county ? ` in ${newestGig.county}` : ''}
          </span>
        </div>
      )}
      {topCategory && (
        <div
          className={`absolute bottom-0 right-0 w-[200px] rounded-card p-[18px] flex flex-col gap-1.5 -rotate-2 ${categoryColour(topCategory.slug)}`}
        >
          <span className="font-display text-[34px] font-extrabold leading-none">{topCategory.open_gig_count}</span>
          <span className="text-[14px]">open gigs in {topCategory.name}</span>
        </div>
      )}
    </div>
  )
}

export default function BrowseHero({ newToday, newestGig, topCategory, search, onSearchChange, onSearchSubmit }) {
  const submit = (e) => {
    e.preventDefault()
    onSearchSubmit()
  }

  return (
    <section className="max-w-page mx-auto px-4 sm:px-8 pt-7 pb-9 flex flex-wrap gap-10 items-center">
      <div className="flex-[999_1_520px] min-w-0 flex flex-col gap-5">
        {newToday > 0 && (
          <span className="self-start inline-flex items-center gap-2 text-[14px] font-semibold text-accent bg-accent-light px-3.5 py-[7px] rounded-pill">
            <span className="w-2 h-2 rounded-full bg-accent-dot" aria-hidden="true" />
            {gigsLabel(newToday)}
          </span>
        )}
        <h1 className="text-[40px] sm:text-display font-extrabold leading-[1.02] tracking-[-0.035em]">
          Work that fits <span className="bg-sun px-2.5 rounded-button box-decoration-clone">your skills</span>, paid
          in KES.
        </h1>
        <p className="text-lead text-ink-soft max-w-[540px]">
          Short projects from businesses across Kenya. Apply in minutes, get paid when the work is done.
        </p>
        <form
          role="search"
          onSubmit={submit}
          className="flex flex-wrap gap-2 bg-surface rounded-tile p-2 shadow-raised max-w-[620px]"
        >
          <label className="flex-[1_1_260px] flex items-center gap-2.5 px-3 min-h-[52px]">
            <Search size={20} strokeWidth={2} className="text-muted shrink-0" aria-hidden="true" />
            <span className="sr-only">Search gigs</span>
            <input
              type="search"
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Try logo design, bookkeeping, TikTok…"
              className="flex-1 min-w-0 border-0 bg-transparent text-body text-ink placeholder:text-muted focus:outline-none"
            />
          </label>
          <button
            type="submit"
            className="min-h-[52px] px-[26px] rounded-button bg-primary text-white text-body font-semibold hover:bg-primary-hover flex-auto sm:flex-none"
          >
            Search gigs
          </button>
        </form>
      </div>
      <HeroCards newestGig={newestGig} topCategory={topCategory} />
    </section>
  )
}
