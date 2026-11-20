from rest_framework import serializers

from accounts.models import User
from accounts.phones import clean_phone

from .models import NotificationPreference, UserSession


class AccountSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone']

    def validate_phone(self, value):
        return clean_phone(value)


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'new_application_email', 'new_application_inapp',
            'status_change_email', 'status_change_inapp',
            'new_match_email', 'new_match_inapp',
            'security_alert_email', 'security_alert_inapp',
            'new_message_email', 'new_message_inapp',
            'invite_email', 'invite_inapp',
        ]


class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = ['id', 'user_agent', 'created_at', 'last_used_at']
