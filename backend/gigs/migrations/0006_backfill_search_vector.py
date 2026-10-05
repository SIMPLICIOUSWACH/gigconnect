from django.contrib.postgres.search import SearchVector
from django.db import migrations
from django.db.models import Value


def backfill(apps, schema_editor):
    Gig = apps.get_model('gigs', 'Gig')
    for gig in Gig.objects.all().iterator():
        skill_names = ' '.join(gig.skills.values_list('name', flat=True))
        vector = (
            SearchVector('title', weight='A')
            + SearchVector(Value(skill_names), weight='B')
            + SearchVector('description', weight='C')
        )
        Gig.objects.filter(pk=gig.pk).update(search_vector=vector)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('gigs', '0005_search_vector_and_indexes'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
