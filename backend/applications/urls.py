from django.urls import path

from .views import (
    ApplicationDetailView,
    ApplicationStatusView,
    GigApplicationsView,
    MyApplicationsView,
    WithdrawApplicationView,
)

urlpatterns = [
    path('gigs/<uuid:gig_id>/applications/', GigApplicationsView.as_view(), name='gig-applications'),
    path('applications/mine/', MyApplicationsView.as_view(), name='my-applications'),
    path('applications/<uuid:pk>/', ApplicationDetailView.as_view(), name='application-detail'),
    path(
        'applications/<uuid:application_id>/withdraw/',
        WithdrawApplicationView.as_view(),
        name='application-withdraw',
    ),
    path(
        'applications/<uuid:application_id>/status/',
        ApplicationStatusView.as_view(),
        name='application-status',
    ),
]
