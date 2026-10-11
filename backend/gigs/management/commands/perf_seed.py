import random
import uuid
from datetime import date, timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models.expressions import RawSQL

from accounts.models import User
from profiles.counties import KENYA_COUNTIES
from profiles.models import Skill

from ...models import Category, Gig, GigSkill

PERF_CLIENT_COUNT = 20
PERF_EMAIL_PREFIX = 'perf-client-'
BATCH_SIZE = 2000
TOP_COUNTIES = ['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Uasin Gishu']

TITLE_TEMPLATES = [
    'Need a {skill} expert for a {business} project',
    '{skill} help needed for our {business}',
    'Looking for a {skill} freelancer, {business} client',
    'Short-term {skill} gig for a {business}',
    '{business} needs ongoing {skill} support',
]
DESCRIPTION_TEMPLATES = [
    'We run a {business} and need someone skilled in {skill}. Experience with {other} is a plus.',
    'Our {business} is growing and we are looking for {skill} help. {other} knowledge would be useful.',
    'A {business} client needs {skill} work done soon. Some {other} is involved.',
]
BUSINESSES = [
    'bakery', 'salon', 'school', 'clinic', 'farm', 'hotel', 'restaurant', 'pharmacy', 'garage',
    'boutique', 'gym', 'cafe', 'hardware shop', 'logistics firm', 'law office', 'church',
    'sacco', 'printing press', 'tour company', 'dairy', 'tailoring shop', 'butchery', 'bookshop',
    'cyber cafe', 'wedding planner', 'real estate agency', 'event venue', 'florist', 'laundry',
    'catering company',
]
BUDGET_BRACKETS = [
    (2000, 5000), (5000, 10000), (8000, 15000), (10000, 20000),
    (15000, 30000), (20000, 40000), (30000, 60000), (50000, 100000),
]
STATUS_WEIGHTS = [
    (Gig.Status.OPEN, 0.90),
    (Gig.Status.IN_PROGRESS, 0.04),
    (Gig.Status.COMPLETED, 0.03),
    (Gig.Status.CLOSED, 0.03),
]


class Command(BaseCommand):
    help = (
        'Fill the database with a large synthetic gig set (default 10,000; use 50000 for the big '
        'run) to measure search and filter performance. Any previous perf_seed gigs are deleted '
        'first, so the size is exact. Development only. Gigs belong to perf-client-* accounts, so '
        '--delete removes them cleanly. Seeded with a fixed random seed, so runs are reproducible.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--size', type=int, default=10_000, help='Number of gigs to have afterwards.')
        parser.add_argument('--seed', type=int, default=42, help='Random seed (default 42).')
        parser.add_argument('--delete', action='store_true', help='Delete the perf_seed gigs and accounts only.')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('perf_seed refuses to run when DEBUG is False.')

        self._delete_existing()
        if options['delete']:
            User.objects.filter(email__startswith=PERF_EMAIL_PREFIX).delete()
            self.stdout.write(self.style.SUCCESS('Deleted perf_seed gigs and accounts.'))
            return

        size = options['size']
        if size < 1:
            raise CommandError('--size must be at least 1.')

        categories = list(Category.objects.all())
        skills = list(Skill.objects.all())
        if not categories or not skills:
            raise CommandError('No categories or skills found. Run `python manage.py migrate` first.')

        rng = random.Random(options['seed'])
        clients = self._ensure_clients()
        today = date.today()
        created = 0

        while created < size:
            batch_size = min(BATCH_SIZE, size - created)
            gigs, links = [], []
            for _ in range(batch_size):
                gig, gig_skills = self._build_gig(rng, clients, categories, skills, today)
                gigs.append(gig)
                links.extend(GigSkill(gig=gig, skill=skill) for skill in gig_skills)
            Gig.objects.bulk_create(gigs)
            GigSkill.objects.bulk_create(links)
            created += batch_size
            self.stdout.write(f'Created {created}/{size}...')

        # bulk_create never fires post_save/m2m_changed, so the search vectors are empty until this.
        call_command('rebuild_search_vectors', stdout=self.stdout)

        # Spread created_at over the last 60 days. auto_now_add overwrites any value passed to
        # bulk_create, so this has to be an UPDATE afterwards.
        Gig.objects.filter(client__email__startswith=PERF_EMAIL_PREFIX).update(
            created_at=RawSQL("now() - random() * interval '60 days'", [])
        )

        # Fresh planner statistics, so EXPLAIN output reflects the real data size.
        with connection.cursor() as cursor:
            cursor.execute(f'ANALYZE {Gig._meta.db_table}')
            cursor.execute(f'ANALYZE {GigSkill._meta.db_table}')

        self.stdout.write(self.style.SUCCESS(f'perf_seed: {size} gig(s) ready.'))

    def _delete_existing(self):
        Gig.objects.filter(client__email__startswith=PERF_EMAIL_PREFIX).delete()

    def _ensure_clients(self):
        clients = []
        for i in range(1, PERF_CLIENT_COUNT + 1):
            email = f'{PERF_EMAIL_PREFIX}{i}@example.test'
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(
                    email=email, password=uuid.uuid4().hex, full_name=f'Perf Client {i}',
                    phone=f'2547{90000000 + i}', role=User.Role.CLIENT,
                    is_email_verified=True, is_profile_complete=True, is_synthetic=True,
                )
            clients.append(user)
        return clients

    def _build_gig(self, rng, clients, categories, skills, today):
        gig_skills = rng.sample(skills, k=min(len(skills), rng.randint(1, 4)))
        primary, other = gig_skills[0].name, rng.choice(skills).name
        business = rng.choice(BUSINESSES)
        budget_min, budget_max = rng.choice(BUDGET_BRACKETS)

        deadline_days = rng.choice([3, 5, 7, 10, 14, 21, 30, 45, 60, 90])
        if rng.random() < 0.05:
            application_deadline = today - timedelta(days=rng.randint(1, 20))  # already closed
        else:
            application_deadline = today + timedelta(days=rng.randint(1, deadline_days))

        roll, status = rng.random(), Gig.Status.OPEN
        cumulative = 0.0
        for candidate, weight in STATUS_WEIGHTS:
            cumulative += weight
            if roll < cumulative:
                status = candidate
                break

        if rng.random() < 0.15:
            county, is_remote = None, True
        else:
            county = rng.choice(TOP_COUNTIES) if rng.random() < 0.7 else rng.choice(KENYA_COUNTIES)
            is_remote = False

        gig = Gig(
            client=rng.choice(clients),
            category=rng.choice(categories),
            title=rng.choice(TITLE_TEMPLATES).format(skill=primary, business=business),
            description=rng.choice(DESCRIPTION_TEMPLATES).format(skill=primary, business=business, other=other),
            budget_min=budget_min,
            budget_max=budget_max,
            deadline=today + timedelta(days=deadline_days),
            application_deadline=application_deadline,
            is_negotiable=rng.random() < 0.7,
            county=county,
            is_remote=is_remote,
            status=status,
            is_synthetic=True,
        )
        return gig, gig_skills
