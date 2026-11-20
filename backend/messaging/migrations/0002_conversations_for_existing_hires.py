from django.db import migrations
from django.db.models import OuterRef, Subquery
from django.db.models.functions import Coalesce


def open_for_existing_hires(apps, schema_editor):
    """Applications hired before chat existed get their conversation too. Quietly: nobody is notified."""
    Application = apps.get_model('applications', 'Application')
    ApplicationStatusEvent = apps.get_model('applications', 'ApplicationStatusEvent')
    Conversation = apps.get_model('messaging', 'Conversation')
    hired = Application.objects.filter(status='hired', conversation__isnull=True).select_related('gig')
    created = Conversation.objects.bulk_create([
        Conversation(application=app, gig=app.gig, client_id=app.gig.client_id, freelancer_id=app.freelancer_id)
        for app in hired
    ])
    # The chat shows "Hired <date>" from created_at, so date each one from the hire, not from today.
    hired_event = ApplicationStatusEvent.objects.filter(application=OuterRef('application'), to_status='hired')
    application = Application.objects.filter(pk=OuterRef('application'))
    Conversation.objects.filter(pk__in=[conversation.pk for conversation in created]).update(
        created_at=Coalesce(
            Subquery(hired_event.order_by('-created_at').values('created_at')[:1]),
            Subquery(application.values('updated_at')[:1]),
        ),
    )


def remove_unused(apps, schema_editor):
    """Going back removes the conversations nobody wrote in, which is what the step above created."""
    Conversation = apps.get_model('messaging', 'Conversation')
    Conversation.objects.filter(messages__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0001_initial'),
        ('applications', '0002_application_moderation_status_application_removed_at_and_more'),
    ]

    operations = [
        migrations.RunPython(open_for_existing_hires, remove_unused),
    ]
