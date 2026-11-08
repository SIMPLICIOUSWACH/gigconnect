from django.urls import path

from . import views

urlpatterns = [
    path('notifications/', views.NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread-count/', views.UnreadCountView.as_view(), name='notification-unread-count'),
    path('notifications/read-all/', views.MarkAllReadView.as_view(), name='notification-read-all'),
    path('notifications/<uuid:pk>/read/', views.MarkReadView.as_view(), name='notification-read'),
]
