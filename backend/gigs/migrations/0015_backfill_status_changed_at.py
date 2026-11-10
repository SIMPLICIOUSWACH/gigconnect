from django.db import migrations
from django.db.models import F


def backfill(apps, schema_editor):
    """Completed and closed gigs from before status_changed_at existed: their last save is the best record there is."""
    Gig = apps.get_model('gigs', 'Gig')
    Gig.objects.filter(status__in=['completed', 'closed'], status_changed_at__isnull=True).update(
        status_changed_at=F('updated_at'),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('gigs', '0014_gig_status_changed_at'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
