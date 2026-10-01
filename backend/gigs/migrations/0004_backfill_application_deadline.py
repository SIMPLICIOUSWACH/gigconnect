from django.db import migrations
from django.db.models import F


def backfill(apps, schema_editor):
    Gig = apps.get_model('gigs', 'Gig')
    Gig.objects.filter(application_deadline__isnull=True).update(application_deadline=F('deadline'))


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('gigs', '0003_gig_application_deadline_gig_is_negotiable'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
