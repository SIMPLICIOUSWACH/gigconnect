from django.contrib import admin

from .models import NotificationPreference, UserSession

admin.site.register(NotificationPreference)
admin.site.register(UserSession)
