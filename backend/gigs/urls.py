from django.urls import path

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
]
