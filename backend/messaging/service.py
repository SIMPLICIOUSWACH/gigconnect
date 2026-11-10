from notifications.models import Notification
from notifications.service import notify

from .models import Conversation


def open_conversation_on_hire(application):
    """
    Open the chat for a hired application (once) and tell the client to start it. Called inside the hire
    transaction, so a hire that fails never leaves a chat behind. Returns the conversation.
    """
    gig = application.gig
    conversation, created = Conversation.objects.get_or_create(
        application=application,
        defaults={'gig': gig, 'client_id': gig.client_id, 'freelancer_id': application.freelancer_id},
    )
    if created:
        name = application.freelancer.full_name
        notify(
            gig.client, Notification.Kind.CHAT_OPENED, f'You hired {name}',
            f'You hired {name} for "{gig.title}". Send them a message to get started.',
            link=f'/messages/{conversation.pk}',
            email_preference='new_message_email', inapp_preference='new_message_inapp',
        )
    return conversation
