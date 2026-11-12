from django.urls import path

from . import chat_views, delete_views, views

urlpatterns = [
    path('stats/', views.StatsView.as_view(), name='admin-stats'),
    path('recommender/', views.RecommenderView.as_view(), name='admin-recommender'),
    path('users/', views.UserListView.as_view(), name='admin-user-list'),
    path('users/<uuid:pk>/', views.UserDetailView.as_view(), name='admin-user-detail'),
    path('users/<uuid:pk>/suspend/', views.SuspendUserView.as_view(), name='admin-user-suspend'),
    path('users/<uuid:pk>/reinstate/', views.ReinstateUserView.as_view(), name='admin-user-reinstate'),
    path(
        'users/<uuid:pk>/delete-preview/', delete_views.UserDeletePreviewView.as_view(),
        name='admin-user-delete-preview',
    ),
    path('users/<uuid:pk>/delete/', delete_views.DeleteUserView.as_view(), name='admin-user-delete'),
    path('verifications/', views.VerificationListView.as_view(), name='admin-verification-list'),
    path('verifications/<uuid:pk>/', views.VerificationDetailView.as_view(), name='admin-verification-detail'),
    path(
        'verifications/<uuid:pk>/document/', views.VerificationDocumentView.as_view(),
        name='admin-verification-document',
    ),
    path('gigs/', views.GigListView.as_view(), name='admin-gig-list'),
    path('gigs/<uuid:pk>/', views.GigDetailView.as_view(), name='admin-gig-detail'),
    path('gigs/<uuid:pk>/remove/', views.RemoveGigView.as_view(), name='admin-gig-remove'),
    path('gigs/<uuid:pk>/restore/', views.RestoreGigView.as_view(), name='admin-gig-restore'),
    path('applications/', views.ApplicationListView.as_view(), name='admin-application-list'),
    path('applications/<uuid:pk>/remove/', views.RemoveApplicationView.as_view(), name='admin-application-remove'),
    path('applications/<uuid:pk>/restore/', views.RestoreApplicationView.as_view(), name='admin-application-restore'),
    path('chat-reports/', chat_views.ChatReportListView.as_view(), name='admin-chat-report-list'),
    path('chat-reports/<uuid:pk>/', chat_views.ChatReportDetailView.as_view(), name='admin-chat-report-detail'),
    path(
        'chat-reports/<uuid:pk>/resolve/', chat_views.ResolveChatReportView.as_view(),
        name='admin-chat-report-resolve',
    ),
    path('audit-log/', views.AuditLogView.as_view(), name='admin-audit-log'),
]
