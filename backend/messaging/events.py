"""What happens around a chat message apart from storing it. Notifications arrive in the next step."""


def message_sent(conversation, message):
    """Called inside the sending transaction."""


def conversation_read(conversation, reader):
    """Called after `reader` marked the other person's messages as read."""
