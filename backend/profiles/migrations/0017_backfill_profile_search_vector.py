from django.contrib.postgres.search import SearchVector
from django.db import migrations
from django.db.models import Value


def backfill(apps, schema_editor):
    """Give every existing freelancer profile its search vector (name, headline, skills, bio)."""
    FreelancerProfile = apps.get_model('profiles', 'FreelancerProfile')
    profiles = FreelancerProfile.objects.select_related('user').prefetch_related('skills')
    for profile in profiles.iterator(chunk_size=500):
        skill_names = ' '.join(skill.name for skill in profile.skills.all())
        vector = (
            SearchVector(Value(profile.user.full_name), weight='A')
            + SearchVector('headline', weight='A')
            + SearchVector(Value(skill_names), weight='B')
            + SearchVector('bio', weight='C')
        )
        FreelancerProfile.objects.filter(pk=profile.pk).update(search_vector=vector)


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0016_talent_search'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
