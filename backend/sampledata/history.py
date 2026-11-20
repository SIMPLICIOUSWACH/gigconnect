"""
Step two of enrich_sample_data: a believable past.

About 70% of sample freelancers get completed gigs (a few get ten or more), each a new gig from a sample client with a
hire, a status history in the right order, a chat opened on the hire, and dates inside the last 12 months in the order
posted, applied, shortlisted, hired, completed. About 80% of completed gigs are rated, mostly 4 and 5 stars with some 3s
and the odd 1 or 2, and about 30% of reviews get a reply. Every sample client ends up with a gig in each of the four
statuses. Sample accounts are given an earlier join date where their history needs it, and the old date is kept in the
ledger.

Every gig and application made here is flagged, so the recommender never trains or is evaluated on any of it. Which
freelancers get history, and how much, depends only on the seed and their email, so reruns make the same choices.
"""

import hashlib
from datetime import timedelta

from accounts.models import User
from applications.transitions import Status
from gigs.models import Category, Gig
from profiles.models import Skill
from reviews.models import Review
from reviews.service import refresh_rating

from . import builders, gigtext, text
from .profiles_fill import group_of, pick_county, sample_users

SHARE_WITH_HISTORY = 0.7
RATING_WEIGHTS = {5: 50, 4: 32, 3: 12, 2: 4, 1: 2}
RATED_SHARE = 0.8
REPLY_SHARE = 0.3
COUNT_WEIGHTS = {1: 14, 2: 16, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6}
NEUTRAL_SUFFIXES = ['That is my honest view.', 'It was okay.', 'Hopefully better next time.', 'Fair enough in the end.',
                    'Just being honest.', 'We are managing.']
DAY = timedelta(days=1)


def days(rng, low, high):
    return timedelta(days=rng.uniform(low, high))


class ReviewVoice:
    """Picks review wording without repeating a line, including lines already in the database."""

    def __init__(self, rng):
        self.rng = rng
        self.used = set(Review.objects.values_list('text', flat=True))

    def pick(self, group, rating):
        if rating >= 4:
            bank, suffixes = gigtext.POSITIVE[group], gigtext.SUFFIXES
        else:
            bank, suffixes = (gigtext.MIXED if rating == 3 else gigtext.LOW), NEUTRAL_SUFFIXES
        fresh = [line for line in bank if line not in self.used]
        if fresh:
            line = self.rng.choice(fresh)
        else:
            base = self.rng.choice(bank)
            options = [f'{base} {suffix}' for suffix in suffixes if f'{base} {suffix}' not in self.used]
            line = self.rng.choice(options)
        self.used.add(line)
        return line


def category_for(categories, skill_name, group):
    return categories[text.SKILL_CATEGORY_OVERRIDE.get(skill_name, text.GROUP_CATEGORY[group])]


def completed_counts(ctx, freelancers):
    """{freelancer id: how many completed gigs}: 70% have some, three of them ten or more, the rest one to eight."""
    ranked = sorted(freelancers, key=lambda u: hashlib.sha256(f'{ctx.seed}:{u.email}'.encode()).hexdigest())
    with_history = ranked[:round(SHARE_WITH_HISTORY * len(ranked))]
    counts = {user.pk: 0 for user in freelancers}
    for position, user in enumerate(with_history):
        rng = ctx.rng('count', user.email)
        counts[user.pk] = rng.randint(10, 12) if position < 3 else rng.choices(
            list(COUNT_WEIGHTS), weights=list(COUNT_WEIGHTS.values()),
        )[0]
    return counts


class Builder:
    def __init__(self, ctx, freelancers, clients):
        self.ctx = ctx
        self.freelancers, self.clients = freelancers, clients
        self.skills = {skill.name: skill for skill in Skill.objects.all()}
        self.categories = {category.name: category for category in Category.objects.all()}
        self.voice = ReviewVoice(ctx.rng('reviews'))
        self.rated = set()

    # -- completed gigs ----------------------------------------------------------------------------------------------

    def gig_skills(self, rng, group, wanted):
        names = [name for name in wanted if text.SKILL_GROUP.get(name) == group][:2]
        if not names:
            names = [rng.choice([n for n, g in text.SKILL_GROUP.items() if g == group])]
        return [self.skills[name] for name in names if name in self.skills]

    def completed_gig(self, freelancer, client, rng):
        ctx = self.ctx
        profile = freelancer.freelancer_profile
        skill_names = [skill.name for skill in profile.skills.all()]
        group = group_of(skill_names)
        skills = self.gig_skills(rng, group, skill_names)
        category = category_for(self.categories, skills[0].name if skills else '', group)
        title, description = rng.choice(gigtext.GIGS[group])
        biz = client.client_profile.company_name or client.full_name
        title, description = title.format(biz=biz), description.format(biz=biz)

        posted = ctx.now - days(rng, 35, 355)
        applied = posted + days(rng, 0.5, 4)
        reviewed = applied + days(rng, 0.3, 2)
        shortlisted = reviewed + days(rng, 0.3, 2)
        hired = shortlisted + days(rng, 0.2, 2)
        completed = min(hired + days(rng, 5, 40), ctx.now - 2 * DAY)

        low, high = text.BUDGET_RANGE[group]
        amount = rng.uniform(low, high)
        budget = (max(500, builders.round_to(amount * rng.uniform(0.6, 0.85))), builders.round_to(amount))
        if budget[0] >= budget[1]:
            budget = (budget[1] - 500, budget[1])
        remote = rng.random() < 0.4
        gig = builders.create_gig(
            ctx, client=client, category=category, title=title, description=description, skills=skills,
            status=Gig.Status.COMPLETED, posted_at=posted, window_days=rng.randint(10, 30),
            delivery_days=max((hired - posted).days + 4, (completed - posted).days + rng.randint(-3, 10)),
            budget=budget, county=None if remote else profile.county, is_remote=remote, changed_at=completed,
        )
        letter = rng.choice(gigtext.LETTERS).format(skill=skills[0].name if skills else 'this', biz=biz)
        rate = builders.round_to(amount * 0.9) if rng.random() < 0.6 else None
        application = builders.add_application(
            ctx, gig, freelancer, applied,
            [(Status.UNDER_REVIEW, reviewed), (Status.SHORTLISTED, shortlisted), (Status.HIRED, hired)],
            cover_letter=letter, proposed_rate=rate,
        )
        builders.open_conversation(ctx, application, hired)
        ctx.touch(freelancer, applied)
        self.turned_down(gig, freelancer, posted, applied, hired, rng)
        self.review(gig, freelancer, group, completed, rng)
        return gig

    def turned_down(self, gig, hired_freelancer, posted, applied, hired, rng):
        """Sometimes someone else applied and was not chosen."""
        if rng.random() >= 0.4:
            return
        other = rng.choice([f for f in self.freelancers if f.pk != hired_freelancer.pk])
        when = posted + days(rng, 0.3, 3)
        steps = [(Status.UNDER_REVIEW, when + days(rng, 0.3, 1)), (Status.REJECTED, hired + days(rng, 0.1, 1))]
        if rng.random() < 0.5:
            steps = steps[1:]
        builders.add_application(
            self.ctx, gig, other, when, steps, cover_letter=rng.choice(gigtext.LETTERS).format(skill='this', biz='you'),
        )

    def review(self, gig, freelancer, group, completed, rng):
        if rng.random() >= RATED_SHARE:
            return
        rating = rng.choices(list(RATING_WEIGHTS), weights=list(RATING_WEIGHTS.values()))[0]
        written = min(completed + days(rng, 0.2, 9), self.ctx.now - timedelta(hours=1))
        reply, reply_at = '', None
        if rng.random() < REPLY_SHARE:
            pool = gigtext.REPLIES[8:10] if rating <= 3 else gigtext.REPLIES[:8] + gigtext.REPLIES[10:]
            reply = rng.choice(pool)
            reply_at = min(written + days(rng, 0.3, 3), self.ctx.now)
        builders.add_review(
            self.ctx, gig, freelancer, rating, self.voice.pick(group, rating), written, reply, reply_at,
        )
        self.rated.add(freelancer.pk)

    # -- the other statuses ---------------------------------------------------------------------------------------

    def random_gig_parts(self, rng, client):
        group = rng.choice(sorted(gigtext.GIGS))
        skills = self.gig_skills(rng, group, [])
        category = category_for(self.categories, skills[0].name if skills else '', group)
        title, description = rng.choice(gigtext.GIGS[group])
        biz = client.client_profile.company_name or client.full_name
        low, high = text.BUDGET_RANGE[group]
        amount = rng.uniform(low, high)
        budget = (max(500, builders.round_to(amount * rng.uniform(0.6, 0.85))), builders.round_to(amount))
        if budget[0] >= budget[1]:
            budget = (budget[1] - 500, budget[1])
        return dict(
            client=client, category=category, title=title.format(biz=biz), description=description.format(biz=biz),
            skills=skills, budget=budget, county=pick_county(rng), is_remote=rng.random() < 0.3,
        ), group, biz, skills

    def applicants(self, gig, rng, how_many, steps_for, posted, biz, skills):
        chosen = rng.sample(self.freelancers, k=min(how_many, len(self.freelancers)))
        for freelancer in chosen:
            applied = posted + days(rng, 0.3, 4)
            builders.add_application(
                self.ctx, gig, freelancer, applied, steps_for(applied, rng),
                cover_letter=rng.choice(gigtext.LETTERS).format(skill=skills[0].name if skills else 'this', biz=biz),
            )

    def open_gig(self, client, rng):
        ctx = self.ctx
        parts, group, biz, skills = self.random_gig_parts(rng, client)
        posted = ctx.now - days(rng, 6, 14)
        left = rng.randint(10, 45)
        gig = builders.create_gig(
            ctx, status=Gig.Status.OPEN, posted_at=posted, window_days=(ctx.now - posted).days + left,
            delivery_days=(ctx.now - posted).days + left + rng.randint(14, 45), **parts,
        )

        def steps(applied, rng):
            path = rng.choice([[], [Status.UNDER_REVIEW], [Status.UNDER_REVIEW, Status.SHORTLISTED]])
            when, steps = applied, []
            for status in path:
                when = when + days(rng, 0.3, 1.5)
                steps.append((status, when))
            return steps

        self.applicants(gig, rng, rng.randint(1, 3), steps, posted, biz, skills)

    def in_progress_gig(self, client, rng):
        ctx = self.ctx
        parts, group, biz, skills = self.random_gig_parts(rng, client)
        posted = ctx.now - days(rng, 25, 70)
        applied = posted + days(rng, 0.5, 4)
        reviewed = applied + days(rng, 0.3, 2)
        shortlisted = reviewed + days(rng, 0.3, 2)
        hired = shortlisted + days(rng, 0.2, 2)
        gig = builders.create_gig(
            ctx, status=Gig.Status.IN_PROGRESS, posted_at=posted, window_days=rng.randint(10, 30),
            delivery_days=(ctx.now - posted).days + rng.randint(5, 40), changed_at=hired, **parts,
        )
        freelancer = rng.choice(self.freelancers)
        application = builders.add_application(
            ctx, gig, freelancer, applied,
            [(Status.UNDER_REVIEW, reviewed), (Status.SHORTLISTED, shortlisted), (Status.HIRED, hired)],
            cover_letter=rng.choice(gigtext.LETTERS).format(skill=skills[0].name if skills else 'this', biz=biz),
        )
        builders.open_conversation(ctx, application, hired)
        self.turned_down(gig, freelancer, posted, applied, hired, rng)

    def closed_gig(self, client, rng):
        ctx = self.ctx
        parts, group, biz, skills = self.random_gig_parts(rng, client)
        posted = ctx.now - days(rng, 45, 150)
        closed = posted + days(rng, 15, 40)
        gig = builders.create_gig(
            ctx, status=Gig.Status.CLOSED, posted_at=posted, window_days=rng.randint(10, 20),
            delivery_days=rng.randint(20, 50), changed_at=closed, **parts,
        )

        def steps(applied, rng):
            if rng.random() < 0.3:
                return [(Status.WITHDRAWN, applied + days(rng, 0.5, 3))]
            return [(Status.UNDER_REVIEW, applied + days(rng, 0.3, 1)), (Status.REJECTED, closed - days(rng, 0.1, 2))]

        self.applicants(gig, rng, rng.randint(1, 2), steps, posted, biz, skills)


def backdate_accounts(ctx):
    """Make accounts join before the first thing in their history. The old date goes in the ledger."""
    for user, first in sorted(ctx.earliest.items(), key=lambda pair: pair[0].email):
        target = first - days(ctx.rng('joined', user.email), 3, 40)
        if target < user.created_at:
            ctx.ledger.remember(user, 'created_at')
            User.objects.filter(pk=user.pk).update(created_at=target)
            ctx.count('accounts given an earlier join date')


def enrich_history(ctx):
    freelancers = list(sample_users(User.Role.FREELANCER))
    clients = list(sample_users(User.Role.CLIENT))
    if not freelancers or not clients:
        return
    builder = Builder(ctx, freelancers, clients)
    counts = completed_counts(ctx, freelancers)
    ledger = ctx.ledger

    for freelancer in freelancers:
        if ledger.is_done(freelancer, 'history'):
            continue
        rng = ctx.rng('history', freelancer.email)
        for _ in range(counts[freelancer.pk]):
            builder.completed_gig(freelancer, rng.choice(clients), rng)
        ledger.mark_done(freelancer, 'history')
        ctx.count('freelancers given completed gigs', 1 if counts[freelancer.pk] else 0)

    with_history = [f for f in freelancers if counts[f.pk]]
    for client in clients:
        if ledger.is_done(client, 'history'):
            continue
        rng = ctx.rng('history', client.email)
        have = set(Gig.objects.filter(client=client).values_list('status', flat=True))
        if Gig.Status.COMPLETED not in have and with_history:
            builder.completed_gig(rng.choice(with_history), client, rng)
        if Gig.Status.OPEN not in have:
            builder.open_gig(client, rng)
        if Gig.Status.IN_PROGRESS not in have:
            builder.in_progress_gig(client, rng)
        if Gig.Status.CLOSED not in have:
            builder.closed_gig(client, rng)
        ledger.mark_done(client, 'history')

    for freelancer in freelancers:
        if freelancer.pk in builder.rated:
            refresh_rating(freelancer)
    backdate_accounts(ctx)

