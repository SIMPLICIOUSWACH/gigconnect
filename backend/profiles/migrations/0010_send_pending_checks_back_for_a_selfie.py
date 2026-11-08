from django.db import migrations

NOTICE_TITLE = 'Add a selfie to finish ID verification'
NOTICE_BODY = "We've added a selfie step to ID verification. Please complete it to finish."


def ask_for_selfies(apps, schema_editor):
    """
    Checks sent in before the selfie step existed wait in the queue without one. Each goes back to "needs a selfie":
    the ID stays, they only add the selfie, and they are told in the app. This writes the in-app notice directly, so
    no email goes out from the migration.
    """
    FreelancerProfile = apps.get_model('profiles', 'FreelancerProfile')
    Notification = apps.get_model('notifications', 'Notification')
    waiting = FreelancerProfile.objects.filter(verification_status='pending').filter(selfie='') | (
        FreelancerProfile.objects.filter(verification_status='pending', selfie__isnull=True)
    )
    for profile in waiting:
        profile.verification_status = 'unverified'
        profile.save(update_fields=['verification_status'])
        Notification.objects.create(
            recipient_id=profile.user_id, kind='verification_selfie_needed', title=NOTICE_TITLE, body=NOTICE_BODY,
            link='/settings/verification',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0009_selfie_and_challenge'),
        ('notifications', '0003_verification_selfie_needed'),
    ]

    operations = [
        migrations.RunPython(ask_for_selfies, migrations.RunPython.noop),
    ]
