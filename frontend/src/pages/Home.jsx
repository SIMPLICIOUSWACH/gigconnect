import { CheckCircle2, MinusCircle, XCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import Button from '../components/Button'
import Card from '../components/Card'

function SplitCTA({ size = 'default' }) {
  const padding = size === 'large' ? 'px-6 py-4' : ''
  return (
    <div className="flex flex-col sm:flex-row gap-4">
      <Link to="/register?role=client">
        <Button className={`w-full sm:w-auto ${padding}`}>I'm hiring  post a gig</Button>
      </Link>
      <Link to="/register?role=freelancer">
        <Button variant="secondary" className={`w-full sm:w-auto ${padding}`}>
          I'm looking for work
        </Button>
      </Link>
    </div>
  )
}

function ExampleGigCard() {
  return (
    <Card variant="elevated" className="max-w-sm">
      <div className="flex items-center justify-between mb-4">
        <span className="text-caption font-medium px-2.5 py-1 rounded-full bg-primary-light text-primary">
          Marketing
        </span>
        <span className="text-caption font-medium px-2.5 py-1 rounded-full bg-accent-light text-accent">
          Open
        </span>
      </div>
      <h3 className="text-section-title text-ink mb-2">Social Media Management for Nairobi Restaurant</h3>
      <p className="text-body text-muted mb-4">KES 15,000 – 25,000 · Nairobi · Posted 2 days ago</p>
      <div className="flex items-center gap-2 pt-4 border-t border-border">
        <span className="text-caption font-medium px-2.5 py-1 rounded-full bg-accent text-white">
          94% match
        </span>
        <span className="text-caption text-muted">based on your skills</span>
      </div>
    </Card>
  )
}

function StepList({ title, steps }) {
  return (
    <div>
      <h3 className="text-section-title text-ink mb-6">{title}</h3>
      <ol className="space-y-6">
        {steps.map((step, i) => (
          <li key={step.title} className="flex gap-4">
            <span className="shrink-0 w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center text-label font-semibold">
              {i + 1}
            </span>
            <div>
              <p className="text-body font-medium text-ink">{step.title}</p>
              <p className="text-body text-muted mt-1">{step.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}

const COMPARISON_ROWS = [
  {
    feature: 'Priced in KES',
    informal: { icon: 'partial', text: 'Ad hoc, negotiated per chat' },
    global: { icon: 'no', text: 'USD only, conversion loss' },
    gigconnect: { icon: 'yes', text: 'Always KES' },
  },
  {
    feature: 'Structured discovery & tracking',
    informal: { icon: 'no', text: 'Scroll and hope in group chats' },
    global: { icon: 'partial', text: 'Yes, but generic categories' },
    gigconnect: { icon: 'yes', text: 'Built around Kenyan gig categories' },
  },
  {
    feature: 'Locally-relevant matching',
    informal: { icon: 'no', text: 'None' },
    global: { icon: 'partial', text: "Generic ML, not tuned to Kenya's market" },
    gigconnect: { icon: 'yes', text: 'Hybrid ML trained on local gig data' },
  },
  {
    feature: 'Who you compete against',
    informal: { icon: 'partial', text: 'Local, but unstructured' },
    global: { icon: 'no', text: 'Freelancers worldwide' },
    gigconnect: { icon: 'yes', text: 'Kenya-focused marketplace' },
  },
]

function ComparisonIcon({ icon }) {
  if (icon === 'yes') return <CheckCircle2 size={18} className="text-accent shrink-0" />
  if (icon === 'no') return <XCircle size={18} className="text-muted shrink-0" />
  return <MinusCircle size={18} className="text-muted shrink-0" />
}

export default function Home() {
  return (
    <div>
      {/* Hero */}
      <section className="max-w-[1100px] mx-auto px-8 pt-16 pb-20">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <h1 className="text-hero text-primary mb-6">
              Kenya's gig marketplace, built for how Kenyans actually hire and get hired.
            </h1>
            <p className="text-body text-muted mb-8 max-w-md">
              GigConnect replaces scattered WhatsApp groups and Facebook pages with structured gig
              posting, KES pricing, and matching tuned to the local market not a global platform
              with a currency converter bolted on.
            </p>
            <SplitCTA size="large" />
          </div>
          <div className="flex justify-center lg:justify-end">
            <ExampleGigCard />
          </div>
        </div>
      </section>

      {/* Problem */}
      <section className="max-w-[1100px] mx-auto px-8 py-16 border-t border-border">
        <h2 className="text-page-title text-primary mb-6">The problem</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <p className="text-body text-ink">
            Kenya's gig economy grew from roughly 638,000 workers in 2019 to 1.9 million by 2022 
            but the tooling hasn't kept up. Gig work is still discovered and coordinated through
            informal WhatsApp groups and Facebook pages: fragmented, unsearchable, and impossible
            for a client to assess an applicant's actual track record.
          </p>
          <p className="text-body text-ink">
            Global platforms like Upwork and Fiverr exist, but they don't fit this market  budgets
            are quoted in USD with no M-Pesa support, freelancers compete against the entire world
            instead of the local market, and the categories and matching are tuned to global demand,
            not Kenyan skills and pricing norms.
          </p>
        </div>
      </section>

      {/* How it works */}
      <section className="max-w-[1100px] mx-auto px-8 py-16 border-t border-border">
        <h2 className="text-page-title text-primary mb-10">How it works</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-16">
          <StepList
            title="If you're hiring"
            steps={[
              { title: 'Post a gig', detail: 'Set your category, county, and budget in KES.' },
              { title: 'Get matched freelancers', detail: 'Ranked by fit to your gig, not just who applied first.' },
              { title: 'Review, hire, and track', detail: 'See applications, hire, and follow progress in one place.' },
            ]}
          />
          <StepList
            title="If you're looking for work"
            steps={[
              { title: 'Build your profile', detail: 'List your skills, portfolio, and get identity-verified.' },
              { title: 'Browse or get matched', detail: 'Find gigs by category and county, or let matching surface them.' },
              { title: 'Apply and track', detail: 'Submit applications and follow their status end to end.' },
            ]}
          />
        </div>
      </section>

      {/* Why GigConnect */}
      <section className="max-w-[1100px] mx-auto px-8 py-16 border-t border-border">
        <h2 className="text-page-title text-primary mb-10">Why GigConnect</h2>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="text-left border-b border-border">
                <th className="py-3 pr-4 text-label text-muted font-medium">Differentiator</th>
                <th className="py-3 px-4 text-label text-muted font-medium">Informal channels</th>
                <th className="py-3 px-4 text-label text-muted font-medium">Global platforms</th>
                <th className="py-3 pl-4 text-label text-primary font-medium">GigConnect</th>
              </tr>
            </thead>
            <tbody>
              {COMPARISON_ROWS.map((row) => (
                <tr key={row.feature} className="border-b border-border">
                  <td className="py-4 pr-4 text-body text-ink font-medium align-top">{row.feature}</td>
                  <td className="py-4 px-4 align-top">
                    <div className="flex items-start gap-2">
                      <ComparisonIcon icon={row.informal.icon} />
                      <span className="text-body text-muted">{row.informal.text}</span>
                    </div>
                  </td>
                  <td className="py-4 px-4 align-top">
                    <div className="flex items-start gap-2">
                      <ComparisonIcon icon={row.global.icon} />
                      <span className="text-body text-muted">{row.global.text}</span>
                    </div>
                  </td>
                  <td className="py-4 pl-4 align-top">
                    <div className="flex items-start gap-2">
                      <ComparisonIcon icon={row.gigconnect.icon} />
                      <span className="text-body text-ink">{row.gigconnect.text}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Final CTA */}
      <section className="max-w-[1100px] mx-auto px-8 py-16 border-t border-border">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div>
            <h2 className="text-page-title text-primary mb-2">Ready to get started?</h2>
            <p className="text-body text-muted">It takes a minute to create an account.</p>
          </div>
          <SplitCTA />
        </div>
      </section>
    </div>
  )
}
