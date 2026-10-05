from django.db import migrations, models


def flag_gigs_of_synthetic_clients(apps, schema_editor):
    """Gigs already created by seed_gigs belong to flagged seed accounts, so mark them too."""
    Gig = apps.get_model('gigs', 'Gig')
    Gig.objects.filter(client__is_synthetic=True).update(is_synthetic=True)


class Migration(migrations.Migration):

    dependencies = [
        ('gigs', '0009_gig_interaction'),
        ('accounts', '0004_flag_existing_seed_users'),
    ]

    operations = [
        migrations.AddField(
            model_name='gig',
            name='is_synthetic',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(flag_gigs_of_synthetic_clients, migrations.RunPython.noop),
    ]
