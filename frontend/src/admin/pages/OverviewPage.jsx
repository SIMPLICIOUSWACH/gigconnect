import { Link } from 'react-router-dom'
import { fetchApplications, fetchGigs, fetchStats, fetchVerifications } from '../api'
import { ErrorBox, PageHeader, RemovedPill, SkeletonBlock } from '../components/ui'
import { formatDate, formatDateTime, formatNumber } from '../format'
import { useAdminData } from '../useAdminData'

const ATTENTION_ITEMS = 5

async function loadOverview() {
  const [stats, verifications, gigs, applications] = await Promise.all([
    fetchStats(),
    fetchVerifications({ page_size: ATTENTION_ITEMS }),
    fetchGigs({ moderation: 'removed', page_size: ATTENTION_ITEMS }),
    fetchApplications({ moderation: 'removed', page_size: ATTENTION_ITEMS }),
  ])
  const removed = [
    ...gigs.results.map((gig) => ({
      key: `gig-${gig.id}`,
      kind: 'Gig',
      title: gig.title,
      to: `/admin/gigs/${gig.id}`,
      at: gig.removed_at,
      reason: gig.removed_reason,
    })),
    ...applications.results.map((app) => ({
      key: `application-${app.id}`,
      kind: 'Application',
      title: `${app.freelancer.full_name} on "${app.gig.title}"`,
      to: `/admin/applications?id=${app.id}`,
      at: app.removed_at,
      reason: app.removed_reason,
    })),
  ]
    .sort((a, b) => new Date(b.at) - new Date(a.at))
    .slice(0, ATTENTION_ITEMS)
  return { stats, verifications: verifications.results, removed }
}

function StatTile({ label, value, note, tint, to }) {
  return (
    <Link to={to} className={`rounded-tile p-5 flex flex-col gap-1 hover:shadow-raised transition-shadow ${tint}`}>
      <span className="text-label">{label}</span>
      <span className="font-display text-[34px] font-extrabold leading-none mt-1">{formatNumber(value)}</span>
      {note && <span className="text-caption mt-1">{note}</span>}
    </Link>
  )
}

function synthetic(count, total) {
  return count > 0 ? `${formatNumber(count)} of these synthetic` : total === 0 ? 'None yet' : ''
}

export function ApplicationsChart({ series }) {
  const width = 600
  const height = 180
  const gap = 4
  const barWidth = (width - gap * (series.length - 1)) / series.length
  const max = Math.max(1, ...series.map((day) => day.count))
  const total = series.reduce((sum, day) => sum + day.count, 0)
  const busiest = series.reduce((best, day) => (day.count > best.count ? day : best), series[0])
  const summary =
    total === 0
      ? 'No applications in the last 30 days.'
      : `${formatNumber(total)} applications in the last 30 days. The busiest day was ${formatDate(busiest.date)} with ${busiest.count}.`

  return (
    <figure>
      <svg viewBox={`0 0 ${width} ${height + 24}`} role="img" aria-label={summary} className="w-full h-auto">
        <line x1="0" x2={width} y1={height} y2={height} className="stroke-divider" strokeWidth="1" />
        {series.map((day, i) => {
          const barHeight = day.count === 0 ? 0 : Math.max(3, (day.count / max) * (height - 12))
          return (
            <rect
              key={day.date}
              x={i * (barWidth + gap)}
              y={height - barHeight}
              width={barWidth}
              height={barHeight}
              rx="3"
              className="fill-primary"
            >
              <title>{`${formatDate(day.date)}: ${day.count}`}</title>
            </rect>
          )
        })}
        <text x="0" y={height + 18} className="fill-muted text-[12px]">
          {formatDate(series[0].date)}
        </text>
        <text x={width} y={height + 18} textAnchor="end" className="fill-muted text-[12px]">
          Today
        </text>
      </svg>
      <figcaption className="text-caption text-muted mt-2">{summary}</figcaption>
    </figure>
  )
}

export default function OverviewPage() {
  const { data, error, loading, reload } = useAdminData(loadOverview, 'overview')

  if (error) return <ErrorBox onRetry={reload}>{error}</ErrorBox>

  return (
    <>
      <PageHeader title="Overview">How GigConnect is doing, and what needs an admin.</PageHeader>

      {loading && !data ? (
        <div aria-label="Loading overview" className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonBlock key={i} className="h-32" />
            ))}
          </div>
          <SkeletonBlock className="h-64" />
        </div>
      ) : (
        <Overview data={data} />
      )}
    </>
  )
}

function Overview({ data }) {
  const { stats, verifications, removed } = data
  return (
    <div className="space-y-6">
      <section aria-label="Totals" className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <StatTile
          label="Users"
          value={stats.users.total}
          note={`${formatNumber(stats.users.by_role.freelancer)} freelancers, ${formatNumber(stats.users.by_role.client)} clients`}
          tint="bg-ocean-light text-ocean-ink"
          to="/admin/users"
        />
        <StatTile
          label="Pending verifications"
          value={stats.verifications.pending}
          note={stats.verifications.pending ? 'Waiting for a decision' : 'Queue is clear'}
          tint="bg-sun-light text-sun-ink"
          to="/admin/verifications"
        />
        <StatTile
          label="Open gigs"
          value={stats.gigs.open}
          note={synthetic(stats.gigs.open_synthetic, stats.gigs.open)}
          tint="bg-mint-light text-mint-ink"
          to="/admin/gigs?status=open"
        />
        <StatTile
          label="Applications, last 30 days"
          value={stats.applications.last_30_days}
          note={synthetic(stats.applications.synthetic_last_30_days, stats.applications.last_30_days)}
          tint="bg-plum-light text-plum-ink"
          to="/admin/applications"
        />
        <StatTile
          label="Hires"
          value={stats.hires.total}
          note={`${formatNumber(stats.hires.last_30_days)} in the last 30 days`}
          tint="bg-coral-light text-coral-ink"
          to="/admin/applications?status=hired"
        />
      </section>

      <section aria-labelledby="chart-heading" className="bg-surface rounded-card shadow-hairline p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
          <h2 id="chart-heading" className="text-section-title text-ink">
            Applications per day
          </h2>
          <p className="text-caption text-muted">
            {formatNumber(stats.users.new_last_30_days)} new sign-ups and {formatNumber(stats.gigs.posted_last_30_days)} gigs
            posted in the same 30 days
          </p>
        </div>
        <ApplicationsChart series={stats.daily_applications} />
      </section>

      <section aria-labelledby="attention-heading">
        <h2 id="attention-heading" className="text-section-heading text-ink mb-3">
          Needs attention
        </h2>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="bg-surface rounded-card shadow-hairline p-6">
            <h3 className="text-section-title text-ink mb-3">Oldest pending verifications</h3>
            {verifications.length === 0 ? (
              <p className="text-body text-muted">No ID checks are waiting.</p>
            ) : (
              <ul className="divide-y divide-line">
                {verifications.map((item) => (
                  <li key={item.id} className="py-2.5 flex items-center justify-between gap-3">
                    <Link to={`/admin/verifications?id=${item.id}`} className="text-body font-semibold text-primary hover:underline truncate">
                      {item.user.full_name}
                    </Link>
                    <span className="text-caption text-muted whitespace-nowrap">
                      {item.verification_submitted_at ? `Sent ${formatDate(item.verification_submitted_at)}` : 'Date not recorded'}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="bg-surface rounded-card shadow-hairline p-6">
            <h3 className="text-section-title text-ink mb-3">Recently removed</h3>
            {removed.length === 0 ? (
              <p className="text-body text-muted">Nothing has been removed.</p>
            ) : (
              <ul className="divide-y divide-line">
                {removed.map((item) => (
                  <li key={item.key} className="py-2.5">
                    <div className="flex items-center gap-2">
                      <RemovedPill />
                      <span className="text-caption text-muted">{item.kind}</span>
                      <span className="text-caption text-muted ml-auto whitespace-nowrap">{formatDateTime(item.at)}</span>
                    </div>
                    <Link to={item.to} className="block mt-1 text-body font-semibold text-primary hover:underline truncate">
                      {item.title}
                    </Link>
                    {item.reason && <p className="text-caption text-ink-soft truncate">{item.reason}</p>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
