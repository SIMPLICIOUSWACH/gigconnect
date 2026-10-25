"""
The demo accounts of the planted world, and the printout that shows what the collaborative part does for them.

Three planted freelancers are given readable names and a known password, one from each of the groups the
collaborative factors recover well: premium, quick_cash and remote_only. Each is the member of their group whose
top 5 live recommendations show the group's habit most clearly. A fourth, brand-new freelancer has skills but no
applications, to show the cold start: content scores only.

Everything here works only in the planted database. The accounts keep the planted email prefix, so they stay out of
any other database by the same rule as the rest of the planted world. The groups still live only in the ground truth
file; the names and emails say nothing about them.
"""

from datetime import date
from types import SimpleNamespace

from django.conf import settings
from django.db import transaction
from django.db.models import Count

from . import hybrid, planted
from .evaluation import modes
from .recommend import recommend

DEMO_PASSWORD = 'DemoPass123!'  # a local demo on synthetic accounts only, listed in the README
DEMO_GROUPS = ('premium', 'quick_cash', 'remote_only')
DEMO_ACCOUNTS = {
    'premium': ('planted-amina@example.test', 'Amina Wanjiru'),
    'quick_cash': ('planted-brian@example.test', 'Brian Otieno'),
    'remote_only': ('planted-cynthia@example.test', 'Cynthia Achieng'),
}
COLD_START_ACCOUNT = ('planted-david@example.test', 'David Kamau')
COLD_START_SKILLS = ('Web Development', 'React')
TOP = 5


class DemoError(Exception):
    """The demo cannot be set up here. The message says why."""


def fits_habit(group, gig):
    """Whether a gig in the database fits a group's habit, by the same rule the generator used (planted.is_habit)."""
    created = gig.created_at.date()
    planned = SimpleNamespace(
        window_days=(gig.application_deadline - created).days, job_days=(gig.deadline - created).days,
        budget_max=float(gig.budget_max), negotiable=gig.is_negotiable, remote=gig.is_remote, client=0,
        category=gig.category.name, skills=(),
    )
    freelancer = SimpleNamespace(group=group, favourite_clients=(), neighbour_category=None, skills=())
    clients = {0: SimpleNamespace(verified=gig.client.is_phone_verified)}
    return planted.is_habit(freelancer, planned, clients)


def require_planted_database():
    if modes.current_mode() != modes.SYNTHETIC_PLANTED:
        raise DemoError('The demo accounts only exist in the planted database. Run with RECOMMENDER_PROFILE=demo.')


def top(model, user, count=TOP):
    return recommend(model, user).results[:count]


def choose_demo_freelancers(model):
    """{group: user} for each demo group: the member whose top 5 fit the habit most, then the highest blend share."""
    from accounts.models import User

    require_planted_database()
    groups = planted.read_ground_truth()
    chosen = {}
    for group in DEMO_GROUPS:
        best, best_key = None, None
        members = User.objects.filter(id__in=[i for i, g in groups.items() if g == group]).order_by('email')
        for user in members:
            outcome = recommend(model, user)
            results = outcome.results[:TOP]
            key = (sum(1 for r in results if fits_habit(group, r.gig)), outcome.weight)
            if best_key is None or key > best_key:
                best, best_key = user, key
        if best is None:
            raise DemoError(f'No planted freelancer is in the {group} group.')
        chosen[group] = best
    return chosen


def create_demo_accounts(model):
    """Name the chosen freelancers, set the demo password, and add the cold-start freelancer. Returns the accounts."""
    from accounts.models import User
    from profiles.models import Skill

    require_planted_database()
    chosen = choose_demo_freelancers(model)
    with transaction.atomic():
        for group, user in chosen.items():
            user.email, user.full_name = DEMO_ACCOUNTS[group]
            user.set_password(DEMO_PASSWORD)
            user.save()
        email, name = COLD_START_ACCOUNT
        newcomer = User(
            email=email, full_name=name, phone='254792000000', role=User.Role.FREELANCER, is_email_verified=True,
            is_profile_complete=True, is_synthetic=True,
        )
        newcomer.set_password(DEMO_PASSWORD)
        newcomer.save()
        newcomer.freelancer_profile.skills.set(Skill.objects.filter(name__in=COLD_START_SKILLS))
    _rename_in_ground_truth(chosen)
    return {**chosen, 'cold_start': newcomer}


def _rename_in_ground_truth(chosen):
    """Keep the email column of the ground truth file in step with the renamed accounts."""
    import csv

    path = modes.planted_directory() / planted.GROUND_TRUTH_FILE
    with open(path, newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    renamed = {str(user.id): user.email for user in chosen.values()}
    for row in rows:
        row['email'] = renamed.get(row['freelancer_id'], row['email'])
    with open(path, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=planted.GROUND_TRUTH_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def open_gig_count():
    from gigs.models import Gig

    return Gig.objects.filter(status=Gig.Status.OPEN, application_deadline__gte=date.today()).count()


def open_gigs_with_applicants():
    from gigs.models import Gig

    return (
        Gig.objects.filter(status=Gig.Status.OPEN, application_deadline__gte=date.today())
        .annotate(applicants=Count('applications')).filter(applicants__gt=0).count()
    )


def _row(recommendation, group):
    gig = recommendation.gig
    created = gig.created_at.date()
    window = (gig.application_deadline - created).days
    closes = (gig.application_deadline - date.today()).days
    collaborative = recommendation.collaborative_score
    fits = '' if group is None else ('yes' if fits_habit(group, gig) else 'no')
    return (
        f'  {gig.title[:34]:34} {int(gig.budget_min):>6}-{int(gig.budget_max):<6} '
        f'{"urgent" if window <= planted.URGENT_WINDOW else "":6} closes in {closes:>2}d  '
        f'{"verified" if gig.client.is_phone_verified else "        "}  {"remote" if gig.is_remote else "      "}  '
        f'content {recommendation.content_score:.3f}  '
        f'collab {"  -  " if collaborative is None else f"{collaborative:.3f}"}  '
        f'score {recommendation.score:.3f}  {fits}'
    )


def demo_lines(model):
    """The printout: each demo account's top 5, and the cold-start check, from the live model and live gigs."""
    from accounts.models import User
    from applications.models import Application

    require_planted_database()
    lines = [
        modes.PLANTED_LABEL,
        f'Profile: {settings.RECOMMENDER_PROFILE}. Largest collaborative weight '
        f'{settings.RECOMMENDER_BLEND_MAX_WEIGHT}, ramp {settings.RECOMMENDER_BLEND_RAMP_GIGS} gigs, cold start below '
        f'{settings.RECOMMENDER_COLD_START_MIN_GIGS}, {settings.RECOMMENDER_SVD_COMPONENTS} factors.',
        f'Open gigs today: {open_gig_count()} ({open_gigs_with_applicants()} of them already have applicants).',
        '',
    ]
    accounts = [(group, *DEMO_ACCOUNTS[group]) for group in DEMO_GROUPS] + [(None, *COLD_START_ACCOUNT)]
    for group, email, name in accounts:
        user = User.objects.filter(email=email).first()
        if user is None:
            lines.append(f'{name} <{email}>: not found. Run refresh_planted_demo.')
            continue
        outcome = recommend(model, user)
        applications = Application.objects.filter(freelancer=user).count()
        habit = f'hidden group {group}' if group else 'new freelancer, no applications'
        lines.append(
            f'{name} <{email}>, {habit}: {applications} applications, {outcome.gigs_interacted_with} different gigs, '
            f'collaborative share {outcome.weight:.0%} (content {1 - outcome.weight:.0%}).'
        )
        lines.append('  title                              budget        urgency closes     client    place   scores'
                     + ('                                  fits habit' if group else ''))
        lines += [_row(r, group) for r in outcome.results[:TOP]]
        if group:
            fits = sum(1 for r in outcome.results[:TOP] if fits_habit(group, r.gig))
            lines.append(f'  {fits} of the top {TOP} fit the {group} habit.')
        lines.append('')
    lines += _share_check(model)
    return lines


def _share_check(model):
    """One freelancer below the cold-start threshold (content only) and one above it (blended), with their share."""
    from accounts.models import User

    threshold = settings.RECOMMENDER_COLD_START_MIN_GIGS
    lines = [f'Cold-start check (threshold {threshold} different gigs):']
    newcomer = User.objects.filter(email=COLD_START_ACCOUNT[0]).first()
    above = User.objects.filter(email=DEMO_ACCOUNTS['premium'][0]).first()
    for label, user in (('below', newcomer), ('above', above)):
        if user is None:
            continue
        outcome = recommend(model, user)
        expected = hybrid.blend_weight(outcome.gigs_interacted_with)
        sources = sorted({r.source for r in outcome.results[:TOP]})
        lines.append(
            f'  {label}: {user.full_name}, {outcome.gigs_interacted_with} gigs, collaborative share '
            f'{outcome.weight:.0%} (expected {expected:.0%}), sources in the top {TOP}: {", ".join(sources) or "none"}.'
        )
    return lines
