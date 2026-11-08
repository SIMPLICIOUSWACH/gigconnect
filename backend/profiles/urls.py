from django.urls import path

from .selfie_views import ChallengeView, SelfieView
from .views import (
    CountyListView,
    PortfolioItemDetailView,
    PortfolioItemListCreateView,
    PrivacyInfoView,
    ProfileCompleteView,
    PublicProfileView,
    SkillListView,
    SubmitVerificationView,
)

urlpatterns = [
    path('meta/counties/', CountyListView.as_view(), name='county-list'),
    path('meta/privacy/', PrivacyInfoView.as_view(), name='privacy-info'),
    path('skills/', SkillListView.as_view(), name='skill-list'),
    path('profiles/<uuid:user_id>/', PublicProfileView.as_view(), name='public-profile'),
    path('profile/complete/', ProfileCompleteView.as_view(), name='profile-complete'),
    path('profile/portfolio-items/', PortfolioItemListCreateView.as_view(), name='portfolio-item-list'),
    path('profile/portfolio-items/<uuid:pk>/', PortfolioItemDetailView.as_view(), name='portfolio-item-detail'),
    path('profile/submit-verification/', SubmitVerificationView.as_view(), name='submit-verification'),
    path('profile/verification/challenge/', ChallengeView.as_view(), name='verification-challenge'),
    path('profile/verification/selfie/', SelfieView.as_view(), name='verification-selfie'),
]
