from django.urls import path

from .views import (
    AdminVerificationDetailView,
    AdminVerificationListView,
    PortfolioItemDetailView,
    PortfolioItemListCreateView,
    ProfileCompleteView,
    SkillListView,
    SubmitVerificationView,
)

urlpatterns = [
    path('skills/', SkillListView.as_view(), name='skill-list'),
    path('profile/complete/', ProfileCompleteView.as_view(), name='profile-complete'),
    path('profile/portfolio-items/', PortfolioItemListCreateView.as_view(), name='portfolio-item-list'),
    path('profile/portfolio-items/<uuid:pk>/', PortfolioItemDetailView.as_view(), name='portfolio-item-detail'),
    path('profile/submit-verification/', SubmitVerificationView.as_view(), name='submit-verification'),
    path('admin/verifications/', AdminVerificationListView.as_view(), name='admin-verification-list'),
    path('admin/verifications/<uuid:pk>/', AdminVerificationDetailView.as_view(), name='admin-verification-detail'),
]
