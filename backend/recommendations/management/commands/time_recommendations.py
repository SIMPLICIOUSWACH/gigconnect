import random
import time
from datetime import date, timedelta
from statistics import median

import numpy as np
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import User
from gigs.models import Category, Gig, GigSkill
from profiles.models import Skill

from ... import registry
from ...candidates import candidate_gigs

URL = '/api/recommendations/'
WORDS = (
    'website', 'logo', 'ledger', 'campaign', 'article', 'survey', 'catalogue', 'inventory', 'booking', 'portal',
    'brochure', 'payroll', 'newsletter', 'workshop', 'dashboard', 'interview', 'storefront', 'manual',
)


class Command(BaseCommand):
    help = (
        'Time /api/recommendations/ through the full request stack for the verified freelancers, optionally with '
        'extra open gigs added first. The extra gigs are added inside a transaction that is rolled back at the end, '
        'so nothing is left in the database. Prints the median, 95th percentile and worst response time.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--extra-open-gigs', type=int, default=0, help='Open gigs to add for the measurement.')
        parser.add_argument('--requests', type=int, default=5, help='Requests per freelancer (default 5).')
        parser.add_argument('--freelancers', type=int, default=33, help='Most freelancers to time (default 33).')
        parser.add_argument('--seed', type=int, default=7)

    def handle(self, *args, **options):
        freelancers = list(
            User.objects.filter(role='freelancer', is_email_verified=True, is_active=True,
                                freelancer_profile__skills__isnull=False)
            .distinct().order_by('email')[:options['freelancers']]
        )
        if not freelancers:
            raise CommandError('There is no verified freelancer with skills to time.')

        with transaction.atomic():
            self._add_gigs(options['extra_open_gigs'], options['seed'])
            result = self._time(freelancers, options['requests'])
            transaction.set_rollback(True)  # the extra gigs never stay

        timings = np.array(result['timings'])
        self.stdout.write(
            f'Open gigs a freelancer could apply to: median {result["candidates"]:g} '
            f'(with {options["extra_open_gigs"]} extra open gigs added for the measurement and removed after).'
        )
        self.stdout.write(f'First request after loading: {result["cold"]:.0f} ms (includes loading the model).')
        self.stdout.write(
            f'{len(timings)} requests from {len(freelancers)} freelancers: median {np.median(timings):.0f} ms, '
            f'95th percentile {np.percentile(timings, 95):.0f} ms, worst {timings.max():.0f} ms, '
            f'{result["queries"]} database queries per request.'
        )

    def _add_gigs(self, count, seed):
        if count <= 0:
            return
        rng = random.Random(seed)
        client = User.objects.filter(role='client').order_by('email').first()
        if client is None:
            raise CommandError('There is no client account to post the extra gigs.')
        categories = list(Category.objects.all())
        skills = list(Skill.objects.all())
        today = date.today()
        gigs = []
        for index in range(count):
            words = rng.sample(WORDS, 3)
            gigs.append(Gig(
                client=client, category=rng.choice(categories),
                title=f'{words[0].title()} {words[1]} job {index}',
                description=f'Help with a {words[0]}, a {words[1]} and a {words[2]} for a small team.',
                budget_min=5000, budget_max=20000, deadline=today + timedelta(days=60),
                application_deadline=today + timedelta(days=30), is_synthetic=True,
            ))
        Gig.objects.bulk_create(gigs, batch_size=1000)
        GigSkill.objects.bulk_create(
            [GigSkill(gig=gig, skill=skill) for gig in gigs for skill in rng.sample(skills, 2)], batch_size=2000,
        )

    def _time(self, freelancers, requests):
        client = APIClient()
        registry.clear_cache()
        client.force_authenticate(freelancers[0])
        start = time.perf_counter()
        first = client.get(URL, HTTP_HOST='localhost')
        cold = (time.perf_counter() - start) * 1000
        if first.status_code != 200 or not first.data.get('available'):
            raise CommandError(f'Recommendations are not available: {first.status_code} {first.data}')

        timings, queries = [], 0
        for user in freelancers:
            client.force_authenticate(user)
            for _ in range(requests):
                with CaptureQueriesContext(connection) as captured:
                    start = time.perf_counter()
                    response = client.get(URL, HTTP_HOST='localhost')
                    timings.append((time.perf_counter() - start) * 1000)
                queries = max(queries, len(captured))
                if response.status_code != 200:
                    raise CommandError(f'The endpoint answered {response.status_code} for {user.email}.')
        candidates = median(candidate_gigs(user).count() for user in freelancers)
        return {'timings': timings, 'cold': cold, 'queries': queries, 'candidates': candidates}
