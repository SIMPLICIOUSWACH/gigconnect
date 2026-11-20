from django.urls import path

from . import views

urlpatterns = [
    path('conversations/', views.ConversationListView.as_view(), name='conversation-list'),
    path('conversations/unread-count/', views.UnreadCountView.as_view(), name='conversation-unread-count'),
    path('conversations/<uuid:pk>/', views.ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<uuid:pk>/messages/', views.MessagesView.as_view(), name='conversation-messages'),
    path('conversations/<uuid:pk>/read/', views.MarkReadView.as_view(), name='conversation-read'),
    path('conversations/<uuid:pk>/report/', views.ReportView.as_view(), name='conversation-report'),
]
