from django.urls import path

from .views import (
    PortfolioItemDetailView,
    PortfolioItemListCreateView,
    ProfileCompleteView,
    SkillListView,
)

urlpatterns = [
    path('skills/', SkillListView.as_view(), name='skill-list'),
    path('profile/complete/', ProfileCompleteView.as_view(), name='profile-complete'),
    path('profile/portfolio-items/', PortfolioItemListCreateView.as_view(), name='portfolio-item-list'),
    path('profile/portfolio-items/<uuid:pk>/', PortfolioItemDetailView.as_view(), name='portfolio-item-detail'),
]
