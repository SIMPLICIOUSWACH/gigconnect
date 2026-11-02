from django.urls import path

from usersettings.token_views import TrackedTokenObtainPairView, TrackedTokenRefreshView

from .views import MeView, RegisterView, VerifyEmailView

urlpatterns = [
    path('me/', MeView.as_view(), name='me'),
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/<str:token>/', VerifyEmailView.as_view(), name='verify-email'),
    path('login/', TrackedTokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TrackedTokenRefreshView.as_view(), name='token-refresh'),
]
