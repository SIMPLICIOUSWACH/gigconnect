from django.urls import path

from .invite_views import GigInviteView, InvitableGigsView, SuggestedFreelancersView
from .views import (
    CategoryListView,
    GigDetailView,
    GigInteractionCreateView,
    GigListCreateView,
    GigStatusUpdateView,
    MyGigsView,
)

urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('gigs/', GigListCreateView.as_view(), name='gig-list-create'),
    path('gigs/mine/', MyGigsView.as_view(), name='gig-mine'),
    path('gigs/<uuid:pk>/', GigDetailView.as_view(), name='gig-detail'),
    path('gigs/<uuid:pk>/status/', GigStatusUpdateView.as_view(), name='gig-status-update'),
    path('gigs/<uuid:gig_id>/interactions/', GigInteractionCreateView.as_view(), name='gig-interaction-create'),
    path(
        'gigs/<uuid:gig_id>/suggested-freelancers/', SuggestedFreelancersView.as_view(),
        name='gig-suggested-freelancers',
    ),
    path('gigs/<uuid:gig_id>/invites/', GigInviteView.as_view(), name='gig-invites'),
    path('freelancers/<uuid:user_id>/invitable-gigs/', InvitableGigsView.as_view(), name='invitable-gigs'),
]
