import random

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from profiles.models import ClientProfile, Skill

FIRST_NAMES = [
    'Wanjiru', 'Otieno', 'Achieng', 'Kamau', 'Njeri', 'Mutua', 'Wafula', 'Chebet',
    'Kiptoo', 'Nyambura', 'Odhiambo', 'Wambui', 'Kilonzo', 'Auma', 'Mwangi', 'Akinyi',
]
LAST_NAMES = [
    'Mwangi', 'Omondi', 'Kariuki', 'Cheruiyot', 'Njoroge', 'Wekesa', 'Kimani', 'Adhiambo',
    'Maina', 'Barasa', 'Kipchumba', 'Muthoni', 'Ochieng', 'Wairimu', 'Rotich', 'Nekesa',
]
COMPANY_WORDS = [
    'Baraka', 'Jua Kali', 'Simba', 'Pwani', 'Nyota', 'Amani', 'Uhuru', 'Kilimo',
    'Savanna', 'Tumaini', 'Zawadi', 'Rafiki',
]
COMPANY_SUFFIXES = ['Ltd', 'Enterprises', 'Traders', 'Solutions', 'Group', 'Ventures']
BIOS = [
    'Experienced professional based in Nairobi, focused on delivering reliable work on time.',
    'Detail-oriented freelancer with a track record of happy clients across East Africa.',
    'Self-taught and always learning — I take on projects I can genuinely deliver well.',
    'Available for both short gigs and longer engagements. Clear communicator.',
    'Kenyan freelancer specialising in fast turnaround without cutting corners.',
]


class Command(BaseCommand):
    help = (
        'Seed synthetic client and freelancer accounts (with profiles and, for freelancers, '
        'skills) for local development and demos. Idempotent — re-running skips accounts that '
        'already exist. Every account it creates is flagged is_synthetic. It does not seed a county.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--count', type=int, default=20,
            help='Number of client accounts and number of freelancer accounts to create (default 20 each).',
        )

    def handle(self, *args, **options):
        count = options['count']
        skills = list(Skill.objects.all())

        if not skills:
            self.stdout.write(self.style.WARNING(
                'No skills found in the database — run `python manage.py migrate` first '
                '(skills are seeded via a data migration).'
            ))
            return

        industries = [choice[0] for choice in ClientProfile.Industry.choices]
        created_clients = self._seed_clients(count, industries)
        created_freelancers = self._seed_freelancers(count, skills)

        self.stdout.write(self.style.SUCCESS(
            f'Created {created_clients} client(s) and {created_freelancers} freelancer(s). '
            f'Accounts that already existed were skipped.'
        ))

    def _random_name(self):
        return f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'

    def _random_phone(self):
        return f'2547{random.randint(10000000, 99999999)}'

    @transaction.atomic
    def _seed_clients(self, count, industries):
        created = 0
        for i in range(1, count + 1):
            email = f'seed-client-{i}@example.test'
            if User.objects.filter(email=email).exists():
                continue
            user = User.objects.create_user(
                email=email,
                password='SeedPass123!',
                full_name=self._random_name(),
                phone=self._random_phone(),
                role=User.Role.CLIENT,
                is_email_verified=True,
                is_profile_complete=True,
                is_synthetic=True,
            )
            profile = user.client_profile
            profile.company_name = f'{random.choice(COMPANY_WORDS)} {random.choice(COMPANY_SUFFIXES)}'
            profile.industry = random.choice(industries)
            profile.save()
            created += 1
        return created

    @transaction.atomic
    def _seed_freelancers(self, count, skills):
        created = 0
        for i in range(1, count + 1):
            email = f'seed-freelancer-{i}@example.test'
            if User.objects.filter(email=email).exists():
                continue
            user = User.objects.create_user(
                email=email,
                password='SeedPass123!',
                full_name=self._random_name(),
                phone=self._random_phone(),
                role=User.Role.FREELANCER,
                is_email_verified=True,
                is_profile_complete=True,
                is_synthetic=True,
            )
            profile = user.freelancer_profile
            profile.bio = random.choice(BIOS)
            profile.save()
            sample_size = min(len(skills), random.randint(1, 4))
            profile.skills.set(random.sample(skills, k=sample_size))
            created += 1
        return created
