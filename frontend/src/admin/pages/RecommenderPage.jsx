import { fetchRecommender } from '../api'
import { ErrorBox, PageHeader, Pill, SkeletonBlock } from '../components/ui'
import { formatDateTime, formatNumber } from '../format'
import { useAdminData } from '../useAdminData'

const METHOD_LABELS = { hybrid: 'Hybrid (live)', content: 'Content only', popularity: 'Most popular', random: 'Random' }
const METRIC_LABELS = { precision: 'Precision', recall: 'Recall', hit: 'Hit rate' }

function Row({ label, children }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-6 gap-y-1 py-2.5 border-b border-line last:border-0">
      <dt className="text-body text-ink-soft">{label}</dt>
      <dd className="text-body text-ink font-semibold text-right">{children}</dd>
    </div>
  )
}

function Panel({ title, children }) {
  return (
    <section className="bg-surface rounded-card shadow-hairline p-6">
      <h2 className="text-section-title text-ink mb-2">{title}</h2>
      {children}
    </section>
  )
}

const percent = (value) => (value === null || value === undefined ? 'Not recorded' : `${(value * 100).toFixed(1)}%`)

export default function RecommenderPage() {
  const { data, error, loading, reload } = useAdminData(fetchRecommender, 'recommender')

  return (
    <>
      <PageHeader title="Recommender">
        The settings the &quot;Picked for you&quot; list is running with. Read only: training and tuning are done with
        management commands, not from here.
      </PageHeader>
      {error && <ErrorBox onRetry={reload}>{error}</ErrorBox>}
      {loading && !data ? <SkeletonBlock className="h-96" /> : data && <Recommender data={data} />}
    </>
  )
}

function Recommender({ data }) {
  const { profile, model, settings, evaluation } = data
  const methods = evaluation ? [...new Set(evaluation.scores.map((score) => score.method))] : []
  const metrics = evaluation ? [...new Set(evaluation.scores.map((score) => score.metric))] : []
  const score = (method, metric) => evaluation.scores.find((row) => row.method === method && row.metric === metric)

  return (
    <div className="grid gap-4 lg:grid-cols-2 items-start">
      <Panel title="Active profile">
        <div className="flex flex-wrap gap-2 mb-3">
          {profile.is_demo ? (
            <Pill tone="sun">Demo profile · synthetic planted data</Pill>
          ) : (
            <Pill tone="mint">Production profile</Pill>
          )}
          <Pill tone={profile.recommendations_enabled ? 'mint' : 'sand'}>
            {profile.recommendations_enabled ? 'Recommendations on' : 'Recommendations off'}
          </Pill>
        </div>
        {profile.label && <p className="text-body text-ink-soft mb-2">{profile.label}</p>}
        <dl>
          <Row label="Profile">{profile.name}</Row>
          <Row label="Database">{profile.database}</Row>
        </dl>
      </Panel>

      <Panel title="Model in use">
        {model ? (
          <dl>
            <Row label="Version">{model.version}</Row>
            <Row label="Trained">{formatDateTime(model.trained_at)}</Row>
            <Row label="Platform gigs">
              {formatNumber(model.platform_gigs)}
              {model.synthetic_platform_gigs > 0 && ` (${formatNumber(model.synthetic_platform_gigs)} synthetic)`}
            </Row>
            <Row label="External job postings">{formatNumber(model.external_documents)}</Row>
            <Row label="Freelancers">{formatNumber(model.freelancers)}</Row>
            <Row label="Collaborative model">
              {model.collaborative_fitted ? `Fitted on ${formatNumber(model.interactions)} pairs` : 'Not fitted'}
            </Row>
            {!model.collaborative_fitted && model.collaborative_skipped_reason && (
              <p className="text-caption text-muted mt-2">{model.collaborative_skipped_reason}</p>
            )}
          </dl>
        ) : (
          <p className="text-body text-muted">No model has been trained yet. Run train_recommender to make one.</p>
        )}
      </Panel>

      <Panel title="Settings">
        <dl>
          <Row label="Collaborative weight (most it reaches)">{settings.blend_max_weight}</Row>
          <Row label="Gigs before it reaches that weight">{settings.blend_ramp_gigs}</Row>
          <Row label="Cold-start threshold (gigs interacted with)">{settings.cold_start_min_gigs}</Row>
          <Row label="Factors (SVD components)">{settings.svd_components}</Row>
          <Row label="Match bands, good / strong">
            {settings.band_good} / {settings.band_strong}
          </Row>
          <Row label="Trains on synthetic data">{settings.include_synthetic ? 'Yes' : 'No'}</Row>
        </dl>
      </Panel>

      <Panel title="Latest evaluation">
        {evaluation ? (
          <>
            <p className="text-caption text-muted mb-3">
              From {evaluation.report}, the {evaluation.part} part, top {evaluation.k}, {formatNumber(evaluation.freelancers)}{' '}
              freelancers.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-left min-w-[360px]">
                <caption className="sr-only">Evaluation scores by method</caption>
                <thead>
                  <tr className="border-b border-line">
                    <th scope="col" className="py-2 text-label text-muted">
                      Method
                    </th>
                    {metrics.map((metric) => (
                      <th key={metric} scope="col" className="py-2 text-label text-muted text-right">
                        {METRIC_LABELS[metric] || metric}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {methods.map((method) => (
                    <tr key={method} className="border-b border-line last:border-0">
                      <th scope="row" className="py-2 text-body text-ink font-semibold">
                        {METHOD_LABELS[method] || method}
                      </th>
                      {metrics.map((metric) => (
                        <td key={metric} className="py-2 text-body text-ink text-right">
                          {percent(score(method, metric)?.mean)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="text-body text-muted">No evaluation report has been recorded for this data yet.</p>
        )}
      </Panel>
    </div>
  )
}
