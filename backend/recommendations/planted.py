"""
The synthetic_planted seed world: freelancers with hidden taste groups, for checking that the collaborative model can
find a pattern when one exists. It is a second seed mode beside the ordinary skill-overlap seed, kept in a database
of its own (see evaluation/modes.py), and it says nothing about real freelancers.

How each freelancer picks the gigs they apply to:

- about 40% by the habits of their hidden group,
- about 40% by skill overlap (gigs that share a skill with them),
- about 20% at random,

every draw weighted by a hidden popularity per gig, so a few gigs get many applicants.

The groups and their habits. A habit only ever looks at things the content model does not read: budget, urgency,
client, location and posting date. It never looks at a title, a description or a skill.

- quick_cash: short application window or short job, and a lower budget
- premium: a higher budget, negotiable, from a client with a verified phone (the only client verification there is)
- remote_only: remote gigs
- client_loyal: gigs from two favourite clients, picked from the ten that post the most
- cross_field: gigs in one neighbouring category that share none of the freelancer's skills. The category name is in
  the gig's text, but nothing in the freelancer's profile points to it, so the content model cannot connect them.

The group of each freelancer is written to datasets/synthetic_planted/ground_truth.csv, never to the database, so no
model can read it. It is read back only to measure how well the collaborative factors recover the groups.

The world is planned first as plain data from a seed (plan_world), so the same seed always gives the same world, and
then written to the database (write_world). Gig text is drawn from its own random stream, from the category and the
skills only, so it cannot carry a habit.
"""

import csv
import json
import random
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta
from statistics import median

from django.db import transaction
from django.utils import timezone

from .evaluation import modes

GROUPS = ('quick_cash', 'premium', 'remote_only', 'client_loyal', 'cross_field')
SHARES = (('habit', 0.4), ('skill', 0.4), ('random', 0.2))

# The skills a gig in each category asks for. The names are the skills the migrations create.
CATEGORY_SKILLS = {
    'Web & Software Development': ('JavaScript', 'Mobile App Development', 'Python', 'React', 'Web Development'),
    'Data & Analytics': ('Bookkeeping', 'Data Entry', 'Excel', 'Python'),
    'Design & Creative': ('Graphic Design', 'UI/UX Design'),
    'Video & Photography': ('Photography', 'Video Editing', 'Videography'),
    'Marketing & Sales': ('Copywriting', 'Digital Marketing', 'Social Media Management'),
    'Writing & Content': ('Content Writing', 'Copywriting', 'Translation'),
    'Admin & Virtual Assistance': ('Bookkeeping', 'Data Entry', 'Event Planning', 'Virtual Assistance'),
    'Local Services': ('Carpentry', 'Electrical Work', 'Plumbing', 'Tailoring'),
}
# The one category next to each, that a cross_field freelancer also applies in.
NEIGHBOURS = {
    'Web & Software Development': 'Data & Analytics',
    'Data & Analytics': 'Admin & Virtual Assistance',
    'Design & Creative': 'Video & Photography',
    'Video & Photography': 'Marketing & Sales',
    'Marketing & Sales': 'Writing & Content',
    'Writing & Content': 'Design & Creative',
    'Admin & Virtual Assistance': 'Local Services',
    'Local Services': 'Web & Software Development',
}
COUNTIES = ('Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Uasin Gishu')
BUDGET_BRACKETS = (
    (2000, 5000), (5000, 10000), (8000, 15000), (10000, 20000),
    (15000, 30000), (20000, 40000), (30000, 60000), (50000, 100000),
)
LOW_BUDGET_MAX = 15000  # a budget_max at or below this is a lower budget
HIGH_BUDGET_MIN = 40000  # a budget_max at or above this is a higher budget
APPLICATION_WINDOWS = (3, 5, 7, 10, 14, 21, 30)  # days a gig takes applications for
URGENT_WINDOW = 7  # a window this short or shorter is urgent
SHORT_JOB = 21  # a job this short or shorter (posting to deadline, in days) is short

# Neutral text: no budget, urgency, place, client or habit word, so the content model cannot see a habit.
TITLE_TEMPLATES = (
    '{skill} project', 'Help with {skill}', '{skill} work', 'A {skill} assignment', '{skill} specialist wanted',
    '{skill} support',
)
DESCRIPTION_TEMPLATE = (
    'Work in {category} that calls for {skills}. '
    'This is planted synthetic data for testing the recommender, not a real gig.'
)
COVER_LETTER = 'This is a planted synthetic application for testing the recommender, not a real application.'
EMAIL_DOMAIN = 'example.test'


class PlantedError(Exception):
    """The planted world cannot be written or read. The message says why."""


@dataclass(frozen=True)
class Sizes:
    freelancers: int = 250
    gigs: int = 300
    clients: int = 60
    favourite_pool: int = 10  # client_loyal freelancers pick their favourites from the clients who post the most
    min_applications: int = 15
    max_applications: int = 25


@dataclass(frozen=True)
class PlannedClient:
    index: int
    verified: bool


@dataclass(frozen=True)
class PlannedFreelancer:
    index: int
    group: str
    home_category: str
    skills: tuple
    neighbour_category: str
    favourite_clients: tuple  # client indexes, only for client_loyal
    county: str


@dataclass(frozen=True)
class PlannedGig:
    index: int
    client: int
    category: str
    skills: tuple
    title: str
    description: str
    budget_min: int
    budget_max: int
    negotiable: bool
    remote: bool
    county: object  # None when remote
    posted_days_ago: float
    window_days: int
    job_days: int
    popularity: float


@dataclass(frozen=True)
class PlannedApplication:
    freelancer: int
    gig: int
    reason: str  # habit, skill or random: how it was picked. Ground truth, never written to the database
    applied_days_ago: float


@dataclass(frozen=True)
class World:
    seed: int
    sizes: Sizes
    clients: tuple
    freelancers: tuple
    gigs: tuple
    applications: tuple


def shares_skill(freelancer, gig):
    return bool(set(freelancer.skills) & set(gig.skills))


def is_habit(freelancer, gig, clients):
    """Whether a gig fits the freelancer's hidden habit. Never looks at title, description or skills, except that
    cross_field excludes gigs sharing a skill, so those applications cannot be explained by skill overlap."""
    group = freelancer.group
    if group == 'quick_cash':
        quick = gig.window_days <= URGENT_WINDOW or gig.job_days <= SHORT_JOB
        return quick and gig.budget_max <= LOW_BUDGET_MAX
    if group == 'premium':
        return gig.budget_max >= HIGH_BUDGET_MIN and gig.negotiable and clients[gig.client].verified
    if group == 'remote_only':
        return gig.remote
    if group == 'client_loyal':
        return gig.client in freelancer.favourite_clients
    if group == 'cross_field':
        return gig.category == freelancer.neighbour_category and not shares_skill(freelancer, gig)
    raise ValueError(f'Unknown group {group}')


def _plan_gigs(rng, text_rng, sizes, categories):
    # A few clients post most of the gigs, which gives client_loyal freelancers shared favourites to be found by.
    client_weights = [1 / (index + 1) ** 0.8 for index in range(sizes.clients)]
    gigs = []
    for index in range(sizes.gigs):
        category = rng.choice(categories)
        options = CATEGORY_SKILLS[category]
        skills = tuple(sorted(rng.sample(options, k=rng.randint(1, 2))))
        low, high = rng.choice(BUDGET_BRACKETS)
        window = rng.choice(APPLICATION_WINDOWS)
        remote = rng.random() < 0.35
        gigs.append(PlannedGig(
            index=index, client=rng.choices(range(sizes.clients), weights=client_weights)[0], category=category,
            skills=skills,
            title=text_rng.choice(TITLE_TEMPLATES).format(skill=skills[0]),
            description=DESCRIPTION_TEMPLATE.format(category=category, skills=' and '.join(skills)),
            budget_min=low, budget_max=high, negotiable=rng.random() < 0.5, remote=remote,
            county=None if remote else rng.choice(COUNTIES), posted_days_ago=round(rng.uniform(10, 150), 4),
            window_days=window, job_days=window + rng.randint(3, 60), popularity=rng.lognormvariate(0, 1.0),
        ))
    return gigs


def _plan_freelancers(rng, sizes, categories):
    groups = [GROUPS[index % len(GROUPS)] for index in range(sizes.freelancers)]
    rng.shuffle(groups)
    freelancers = []
    for index, group in enumerate(groups):
        home = rng.choice(categories)
        options = CATEGORY_SKILLS[home]
        favourites = ()
        if group == 'client_loyal':
            favourites = tuple(sorted(rng.sample(range(min(sizes.favourite_pool, sizes.clients)), k=2)))
        freelancers.append(PlannedFreelancer(
            index=index, group=group, home_category=home,
            skills=tuple(sorted(rng.sample(options, k=rng.randint(1, min(3, len(options)))))),
            neighbour_category=NEIGHBOURS[home], favourite_clients=favourites, county=rng.choice(COUNTIES),
        ))
    return freelancers


def _plan_applications(seed, sizes, freelancers, gigs, clients):
    applications = []
    reasons = [reason for reason, _ in SHARES]
    weights = [share for _, share in SHARES]
    for freelancer in freelancers:
        # Each freelancer has their own stream, so one freelancer's choices never depend on another's.
        rng = random.Random(f'planted-{seed}-applications-{freelancer.index}')
        pools = {
            'habit': [gig for gig in gigs if is_habit(freelancer, gig, clients)],
            'skill': [gig for gig in gigs if shares_skill(freelancer, gig)],
            'random': gigs,
        }
        taken = set()
        for _ in range(rng.randint(sizes.min_applications, sizes.max_applications)):
            reason = rng.choices(reasons, weights=weights)[0]
            available = [gig for gig in pools[reason] if gig.index not in taken]
            if not available:  # the habit or skill gigs have run out: fall back to any gig
                reason, available = 'random', [gig for gig in gigs if gig.index not in taken]
            if not available:
                break
            gig = rng.choices(available, weights=[g.popularity for g in available])[0]
            taken.add(gig.index)
            # A moment inside the gig's application window, and never in the future.
            open_for = min(gig.window_days, gig.posted_days_ago)
            applied = gig.posted_days_ago - rng.random() * open_for
            applications.append(PlannedApplication(freelancer.index, gig.index, reason, round(applied, 6)))
    return applications


def plan_world(seed=42, sizes=None):
    """The whole planted world as plain data. The same seed and sizes always give the same world."""
    sizes = sizes or Sizes()
    rng = random.Random(f'planted-{seed}')
    text_rng = random.Random(f'planted-{seed}-text')  # its own stream, so text cannot depend on any habit draw
    categories = sorted(CATEGORY_SKILLS)
    clients = [PlannedClient(index=index, verified=rng.random() < 0.5) for index in range(sizes.clients)]
    gigs = _plan_gigs(rng, text_rng, sizes, categories)
    freelancers = _plan_freelancers(rng, sizes, categories)
    applications = _plan_applications(seed, sizes, freelancers, gigs, clients)
    return World(
        seed=seed, sizes=sizes, clients=tuple(clients), freelancers=tuple(freelancers), gigs=tuple(gigs),
        applications=tuple(applications),
    )


def summarise(world):
    """Counts that show the world has the shape it was asked for."""
    per_gig = {gig.index: 0 for gig in world.gigs}
    per_freelancer = {freelancer.index: 0 for freelancer in world.freelancers}
    reasons = {reason: 0 for reason, _ in SHARES}
    for application in world.applications:
        per_gig[application.gig] += 1
        per_freelancer[application.freelancer] += 1
        reasons[application.reason] += 1
    groups = {group: sum(1 for f in world.freelancers if f.group == group) for group in GROUPS}
    total = len(world.applications)
    return {
        'seed': world.seed,
        'freelancers': len(world.freelancers), 'gigs': len(world.gigs), 'clients': len(world.clients),
        'applications': total,
        'applications_per_freelancer': (min(per_freelancer.values()), median(per_freelancer.values()),
                                        max(per_freelancer.values())),
        'applicants_per_gig': (min(per_gig.values()), median(per_gig.values()), max(per_gig.values())),
        'reason_shares': {reason: count / total for reason, count in reasons.items()} if total else {},
        'groups': groups,
    }


GROUND_TRUTH_FILE = 'ground_truth.csv'
WORLD_FILE = 'world.json'
GROUND_TRUTH_COLUMNS = ['freelancer_id', 'email', 'group', 'home_category', 'neighbour_category', 'favourite_clients']


def client_email(index):
    return f'{modes.PLANTED_EMAIL_PREFIX}client-{index:03d}@{EMAIL_DOMAIN}'


def freelancer_email(index):
    return f'{modes.PLANTED_EMAIL_PREFIX}freelancer-{index:03d}@{EMAIL_DOMAIN}'


def check_database_is_free():
    """Planted rows only go into a database of their own, so they can never mix with other data."""
    from accounts.models import User

    if User.objects.exclude(email__startswith=modes.PLANTED_EMAIL_PREFIX).exists():
        raise PlantedError(
            'This database holds accounts that are not planted, so the planted world will not be written into it. '
            'Create an empty database for it (see docs/api-endpoints.md) and run with DB_NAME set to it.'
        )
    if User.objects.filter(email__startswith=modes.PLANTED_EMAIL_PREFIX).exists():
        raise PlantedError('A planted world is already here. Run seed_planted --delete first to make a new one.')


def _at(now, days_ago):
    return now - timedelta(days=days_ago)


def _end_of_day(day):
    return timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min))


def write_world(world, now=None):
    """
    Write a planned world to the database and its ground truth to datasets/synthetic_planted/. Returns
    {'freelancers': {index: user id}, 'clients': {index: user id}, 'gigs': {index: gig id}}.
    """
    from accounts.models import User
    from applications.models import Application, ApplicationStatusEvent
    from applications.transitions import Status
    from gigs.models import Category, Gig
    from profiles.models import Skill

    check_database_is_free()
    now = now or timezone.now()
    categories = {category.name: category for category in Category.objects.filter(name__in=CATEGORY_SKILLS)}
    wanted_skills = {name for names in CATEGORY_SKILLS.values() for name in names}
    skills = {skill.name: skill for skill in Skill.objects.filter(name__in=wanted_skills)}
    missing = sorted(set(CATEGORY_SKILLS) - set(categories)) + sorted(wanted_skills - set(skills))
    if missing:
        raise PlantedError(f'These categories or skills are missing, so run migrate first: {", ".join(missing)}.')

    with transaction.atomic():
        clients = {}
        for client in world.clients:
            user = User(
                email=client_email(client.index), full_name=f'Planted Client {client.index}',
                phone=f'2547{90000000 + client.index}', role=User.Role.CLIENT, is_email_verified=True,
                is_phone_verified=client.verified, is_profile_complete=True, is_synthetic=True,
            )
            user.set_unusable_password()  # nobody signs in as a planted account
            user.save()  # the signals make the profile and notification settings, as for any account
            user.client_profile.company_name = f'Planted Company {client.index}'
            user.client_profile.save()
            clients[client.index] = user

        freelancers = {}
        for freelancer in world.freelancers:
            user = User(
                email=freelancer_email(freelancer.index), full_name=f'Planted Freelancer {freelancer.index}',
                phone=f'2547{91000000 + freelancer.index}', role=User.Role.FREELANCER, is_email_verified=True,
                is_profile_complete=True, is_synthetic=True,
            )
            user.set_unusable_password()
            user.save()
            profile = user.freelancer_profile
            profile.county = freelancer.county
            profile.save()
            profile.skills.set([skills[name] for name in freelancer.skills])
            freelancers[freelancer.index] = user

        gigs = {}
        for planned in world.gigs:
            posted = _at(now, planned.posted_days_ago)
            gig = Gig.objects.create(
                client=clients[planned.client], category=categories[planned.category], title=planned.title,
                description=planned.description, budget_min=planned.budget_min, budget_max=planned.budget_max,
                deadline=(posted + timedelta(days=planned.job_days)).date(),
                application_deadline=(posted + timedelta(days=planned.window_days)).date(),
                is_negotiable=planned.negotiable, county=planned.county, is_remote=planned.remote, is_synthetic=True,
                status=Gig.Status.OPEN,
            )
            gig.skills.set([skills[name] for name in planned.skills])
            gig.created_at = gig.updated_at = posted
            gigs[planned.index] = gig
        Gig.objects.bulk_update(list(gigs.values()), ['created_at', 'updated_at'])

        rows = []
        for planned in world.applications:
            gig = gigs[planned.gig]
            last_moment = _end_of_day(gig.application_deadline) - timedelta(seconds=1)
            applied = min(_at(now, planned.applied_days_ago), now, last_moment)
            rows.append(Application(
                gig=gig, freelancer=freelancers[planned.freelancer], cover_letter=COVER_LETTER,
                status=Status.PENDING, is_synthetic=True, created_at=applied, updated_at=applied,
            ))
        when = [row.created_at for row in rows]
        created = Application.objects.bulk_create(rows, batch_size=1000)
        for application, moment in zip(created, when):  # bulk_create stamps "now", so put the planned time back
            application.created_at = application.updated_at = moment
        Application.objects.bulk_update(created, ['created_at', 'updated_at'], batch_size=1000)
        events = ApplicationStatusEvent.objects.bulk_create([
            ApplicationStatusEvent(
                application=application, from_status='', to_status=Status.PENDING,
                changed_by_id=application.freelancer_id,
            )
            for application in created
        ], batch_size=1000)
        for event, application in zip(events, created):
            event.created_at = application.created_at
        ApplicationStatusEvent.objects.bulk_update(events, ['created_at'], batch_size=1000)

    write_ground_truth(world, freelancers)
    return {
        'freelancers': {index: user.id for index, user in freelancers.items()},
        'clients': {index: user.id for index, user in clients.items()},
        'gigs': {index: gig.id for index, gig in gigs.items()},
    }


def write_ground_truth(world, freelancers):
    """The hidden groups, in a file and never in the database."""
    folder = modes.planted_directory()
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / GROUND_TRUTH_FILE, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=GROUND_TRUTH_COLUMNS)
        writer.writeheader()
        for freelancer in world.freelancers:
            writer.writerow({
                'freelancer_id': freelancers[freelancer.index].id, 'email': freelancer_email(freelancer.index),
                'group': freelancer.group, 'home_category': freelancer.home_category,
                'neighbour_category': freelancer.neighbour_category,
                'favourite_clients': ';'.join(client_email(index) for index in freelancer.favourite_clients),
            })
    summary = summarise(world)
    summary['sizes'] = asdict(world.sizes)
    summary['written_at'] = timezone.now().isoformat()
    summary['label'] = modes.PLANTED_LABEL
    (folder / WORLD_FILE).write_text(json.dumps(summary, indent=2, default=str), encoding='utf-8')


def read_ground_truth():
    """{freelancer id (UUID): group}. Read only to score how well the groups were recovered, after fitting."""
    path = modes.planted_directory() / GROUND_TRUTH_FILE
    if not path.is_file():
        raise PlantedError(f'No planted ground truth at {path}. Run seed_planted first.')
    with open(path, newline='', encoding='utf-8') as handle:
        return {uuid.UUID(row['freelancer_id']): row['group'] for row in csv.DictReader(handle)}


def delete_world():
    """Remove every planted row and the ground truth. Returns how many accounts were removed."""
    from accounts.models import User
    from applications.models import Application
    from gigs.models import Gig

    planted = User.objects.filter(email__startswith=modes.PLANTED_EMAIL_PREFIX)
    with transaction.atomic():
        Application.objects.filter(freelancer__in=planted).delete()
        Gig.objects.filter(client__in=planted).delete()
        count = planted.count()
        planted.delete()
    for name in (GROUND_TRUTH_FILE, WORLD_FILE):
        path = modes.planted_directory() / name
        if path.is_file():
            path.unlink()
    return count
