export default function About() {
  return (
    <div className="max-w-[1100px] mx-auto px-8 py-16">
      <h1 className="text-page-title text-primary mb-10">About GigConnect</h1>

      <div className="max-w-[65ch] space-y-8">
        <section>
          <h2 className="text-section-title text-ink mb-3">What this is</h2>
          <p className="text-body text-ink">
            GigConnect is a web-based gig marketplace built for the Kenyan digital labour market.
            Right now, gig work in Kenya is coordinated almost entirely through informal
            channels  WhatsApp groups, Facebook pages  which are fragmented, unsearchable, and
            give a client no structured way to assess who they're hiring. Global platforms like
            Upwork and Fiverr exist, but they don't fit this market: budgets are quoted in USD,
            freelancers compete against the entire world instead of the local market, and the
            categories and matching are tuned to global demand rather than Kenyan skills and
            pricing norms. GigConnect centralises gig posting and applications in one place,
            priced and structured for this market specifically.
          </p>
        </section>

        <section>
          <h2 className="text-section-title text-ink mb-3">Who it's for</h2>
          <p className="text-body text-ink">
            <strong className="text-ink">Clients</strong>  individuals or small businesses who
            need work done (a logo, a website, social media management, event help) and want a
            structured way to post it, see who's applying, and track the work, instead of posting
            in a group chat and hoping someone reliable replies.
          </p>
          <p className="text-body text-ink mt-4">
            <strong className="text-ink">Freelancers</strong>  people offering skilled or
            trade work who want their profile, portfolio, and application history to actually
            count for something, rather than starting from zero in every new WhatsApp thread they
            find themselves in.
          </p>
        </section>

        <section>
          <h2 className="text-section-title text-ink mb-3">What makes the matching different</h2>
          <p className="text-body text-ink">
            GigConnect's recommendation engine is a hybrid of two approaches. When a freelancer is
            new and has no history yet, gigs are matched based on how closely the gig's description
            matches their listed skills  so recommendations work from day one instead of requiring
            weeks of activity first. As a freelancer applies to more gigs, the system gradually
            leans more on patterns from similar freelancers' application history, the same way a
            person familiar with the local market would learn what tends to go together. Both parts
            are trained on Kenyan gig data specifically, not adapted from a global platform's
            dataset  that's the actual difference, not just a marketing claim.
          </p>
        </section>

        <section>
          <h2 className="text-section-title text-ink mb-3">A note on what this is</h2>
          <p className="text-body text-ink">
            GigConnect is a capstone project for a BSc in Informatics & Computer Science at
            Strathmore University not an established company. It's being built and documented
            openly as a real, working product because that's the most honest way to demonstrate
            the engineering, not because it's already operating at scale. If you're evaluating it,
            treat it as a functioning prototype under active development.
          </p>
        </section>
      </div>
    </div>
  )
}
