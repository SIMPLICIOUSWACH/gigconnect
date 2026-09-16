from django.db import migrations


def backfill(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    NotificationPreference = apps.get_model('usersettings', 'NotificationPreference')
    for user in User.objects.filter(notification_preference__isnull=True):
        NotificationPreference.objects.create(user=user)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('usersettings', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
