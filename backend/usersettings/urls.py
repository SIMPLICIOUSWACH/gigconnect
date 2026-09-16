from django.urls import path

from .views import (
    AccountSettingsView,
    ChangePasswordView,
    DeleteAccountView,
    ExportDataView,
    LogoutAllView,
    NotificationPreferenceView,
    SessionListView,
    SessionRevokeView,
)

urlpatterns = [
    path('settings/account/', AccountSettingsView.as_view(), name='settings-account'),
    path('settings/change-password/', ChangePasswordView.as_view(), name='settings-change-password'),
    path('settings/sessions/', SessionListView.as_view(), name='settings-sessions'),
    path('settings/sessions/<uuid:pk>/', SessionRevokeView.as_view(), name='settings-session-revoke'),
    path('settings/sessions/logout-all/', LogoutAllView.as_view(), name='settings-logout-all'),
    path('settings/notifications/', NotificationPreferenceView.as_view(), name='settings-notifications'),
    path('settings/export-data/', ExportDataView.as_view(), name='settings-export-data'),
    path('settings/delete-account/', DeleteAccountView.as_view(), name='settings-delete-account'),
]
