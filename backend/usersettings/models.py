import uuid

from django.conf import settings
from django.db import models


class NotificationPreference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preference'
    )
    new_application_email = models.BooleanField(default=True)
    new_application_inapp = models.BooleanField(default=True)
    status_change_email = models.BooleanField(default=True)
    status_change_inapp = models.BooleanField(default=True)
    new_match_email = models.BooleanField(default=True)
    new_match_inapp = models.BooleanField(default=True)
    security_alert_email = models.BooleanField(default=True)
    security_alert_inapp = models.BooleanField(default=True)

    def __str__(self):
        return f'NotificationPreference<{self.user.email}>'


class UserSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sessions')
    jti = models.CharField(max_length=255, unique=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_used_at']

    def __str__(self):
        return f'UserSession<{self.user.email}:{self.jti[:8]}>'
