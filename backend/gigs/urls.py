from django.urls import path

from .views import (
    CategoryListView,
    GigDetailView,
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
]
