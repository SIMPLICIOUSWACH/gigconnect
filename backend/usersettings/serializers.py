from rest_framework import serializers

from accounts.models import User

from .models import NotificationPreference, UserSession


class AccountSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone']


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'new_application_email', 'new_application_inapp',
            'status_change_email', 'status_change_inapp',
            'new_match_email', 'new_match_inapp',
            'security_alert_email', 'security_alert_inapp',
        ]


class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = ['id', 'user_agent', 'created_at', 'last_used_at']
