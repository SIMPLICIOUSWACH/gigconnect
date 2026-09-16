from django.urls import path

from usersettings.token_views import TrackedTokenObtainPairView, TrackedTokenRefreshView

from .views import RegisterView, SendOTPView, VerifyEmailView, VerifyOTPView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/<str:token>/', VerifyEmailView.as_view(), name='verify-email'),
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('login/', TrackedTokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TrackedTokenRefreshView.as_view(), name='token-refresh'),
]
