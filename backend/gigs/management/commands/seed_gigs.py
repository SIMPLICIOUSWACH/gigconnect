import random
from datetime import date, timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from profiles.models import Skill

from ...models import Category, Gig

# Seeded gigs are placed in real counties (Eldoret is in Uasin Gishu) or marked remote.
LOCATIONS = ['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Uasin Gishu', 'remote']

TITLE_TEMPLATES = [
    'Need a {skill} expert for a {location} based project',
    '{skill} help needed urgently',
    'Looking for a {skill} freelancer in {location}',
    'Short-term {skill} gig',
    '{skill} project for a growing business',
    'One-off {skill} task',
    'Ongoing {skill} support needed',
    '{location} client needs {skill} help',
]

DESCRIPTION_TEMPLATE = (
    'We are a small business based in {location} looking for someone skilled in {skill}. '
    'This is sample seed data generated for testing search and pagination, not a real gig.'
)

BUDGET_BRACKETS = [
    (2000, 5000), (5000, 10000), (8000, 15000), (10000, 20000),
    (15000, 30000), (20000, 40000), (30000, 60000), (50000, 100000),
]

# Mostly a normal spread of deadlines, with a deliberate slice landing inside the next
# 3 days so the frontend's "Urgent" badge (computed client-side from application_deadline)
# has real data to trigger on.
DEADLINE_DAY_OPTIONS = [3, 5, 7, 10, 14, 21, 30, 45, 60, 90]


class Command(BaseCommand):
    help = (
        'Seed ~300 realistic, clearly-fake gigs (Kenyan context: KES budgets, '
        'Nairobi/Mombasa/remote mentions, spread of categories/skills/deadlines) for testing '
        'search and pagination at volume. Development only. Seeded gigs belong to the '
        'seed-client-* accounts from seed_data, so --delete can remove them cleanly.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=300, help='Number of gigs to create (default 300).')
        parser.add_argument(
            '--delete', action='store_true',
            help='Delete all previously seeded gigs instead of creating any.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('seed_gigs refuses to run when DEBUG is False.')

        if options['delete']:
            deleted, _ = Gig.objects.filter(client__email__startswith='seed-client-').delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} seeded row(s) (gigs + related).'))
            return

        clients = list(User.objects.filter(email__startswith='seed-client-', role=User.Role.CLIENT))
        if not clients:
            raise CommandError(
                'No seed client accounts found. Run `python manage.py seed_data` first.'
            )

        categories = list(Category.objects.all())
        skills = list(Skill.objects.all())
        if not categories or not skills:
            raise CommandError('No categories or skills found — run `python manage.py migrate` first.')

        today = date.today()
        created = 0

        for _ in range(options['count']):
            client = random.choice(clients)
            category = random.choice(categories)
            skill_sample = random.sample(skills, k=min(len(skills), random.randint(1, 3)))
            location = random.choice(LOCATIONS)
            primary_skill = skill_sample[0].name

            title = random.choice(TITLE_TEMPLATES).format(skill=primary_skill, location=location)
            description = DESCRIPTION_TEMPLATE.format(skill=primary_skill, location=location)

            budget_min, budget_max = random.choice(BUDGET_BRACKETS)

            deadline_days = random.choice(DEADLINE_DAY_OPTIONS)
            deadline = today + timedelta(days=deadline_days)

            if random.random() < 0.2:
                # Deliberately urgent: application closes within the next 1-3 days.
                application_deadline = today + timedelta(days=random.choice([1, 2, 3]))
            else:
                application_deadline = today + timedelta(days=random.randint(1, deadline_days))

            gig = Gig.objects.create(
                client=client,
                category=category,
                title=title,
                description=description,
                budget_min=budget_min,
                budget_max=budget_max,
                deadline=deadline,
                application_deadline=application_deadline,
                is_negotiable=random.random() < 0.7,
                county=None if location == 'remote' else location,
                is_remote=location == 'remote',
                is_synthetic=True,
                status=Gig.Status.OPEN,
            )
            gig.skills.set(skill_sample)
            created += 1

        # Belt-and-braces: the post_save/m2m_changed signals already keep search_vector current
        # for the create()/skills.set() calls above, but calling the rebuild here means this
        # command stays correct even if it's ever switched to bulk_create for speed.
        call_command('rebuild_search_vectors')

        self.stdout.write(self.style.SUCCESS(f'Created {created} seeded gig(s).'))
