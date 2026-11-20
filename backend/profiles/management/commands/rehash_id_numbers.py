from django.core.management.base import BaseCommand

from profiles.id_privacy import fingerprint_fields
from profiles.models import FreelancerProfile


class Command(BaseCommand):
    help = (
        'Work out the keyed hash of every ID number still stored, with the current ID_HASH_KEY. Run it once after '
        'setting or changing ID_HASH_KEY. Numbers already deleted by purge_id_images or account deletion cannot be '
        'hashed again, so their old hashes stay as they are.'
    )

    def handle(self, *args, **options):
        updated = 0
        for profile in FreelancerProfile.objects.exclude(id_number=''):
            fields = fingerprint_fields(profile.id_number)
            if fields['id_number_hash'] != profile.id_number_hash:
                for name, value in fields.items():
                    setattr(profile, name, value)
                profile.save(update_fields=list(fields))
                updated += 1
        gone = FreelancerProfile.objects.filter(id_number='').exclude(id_number_hash='').count()
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} hash(es).'))
        if gone:
            self.stdout.write(self.style.WARNING(
                f'{gone} hash(es) belong to numbers already deleted and could not be updated.'
            ))
