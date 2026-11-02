from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'kind', 'title', 'body', 'link', 'is_read', 'read_at', 'created_at']

    def get_is_read(self, obj):
        return obj.read_at is not None
