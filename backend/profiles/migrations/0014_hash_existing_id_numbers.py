import hashlib
import hmac
import re

from django.conf import settings
from django.db import migrations


def key():
    # The same rule as profiles/id_privacy.py at the time of writing.
    if settings.ID_HASH_KEY:
        return settings.ID_HASH_KEY.encode()
    return hashlib.sha256(f'gigconnect-id-hash:{settings.SECRET_KEY}'.encode()).digest()


def hash_existing(apps, schema_editor):
    """ID numbers sent before the hash existed get one now, so duplicate checks cover them too."""
    FreelancerProfile = apps.get_model('profiles', 'FreelancerProfile')
    for profile in FreelancerProfile.objects.exclude(id_number='').filter(id_number_hash=''):
        number = re.sub(r'[\s\-./]', '', profile.id_number).upper()
        profile.id_number_hash = hmac.new(key(), number.encode(), hashlib.sha256).hexdigest()
        profile.id_number_last3 = number[-3:]
        profile.save(update_fields=['id_number_hash', 'id_number_last3'])


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0013_id_number_hash_and_purge'),
    ]

    operations = [
        migrations.RunPython(hash_existing, migrations.RunPython.noop),
    ]
