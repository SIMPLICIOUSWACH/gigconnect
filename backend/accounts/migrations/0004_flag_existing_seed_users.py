from django.db import migrations


def flag_seed_users(apps, schema_editor):
    """Accounts made by seed_data before this flag existed (seed-client-N@example.test and
    seed-freelancer-N@example.test) are synthetic too."""
    User = apps.get_model('accounts', 'User')
    User.objects.filter(email__startswith='seed-', email__endswith='@example.test').update(is_synthetic=True)


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0003_is_synthetic'),
    ]

    operations = [
        migrations.RunPython(flag_seed_users, migrations.RunPython.noop),
    ]
