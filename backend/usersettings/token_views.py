from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import UserSession


class TrackedTokenObtainPairView(TokenObtainPairView):
    """Same as SimpleJWT's login view, but records a UserSession row per issued refresh token."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            refresh = RefreshToken(response.data['refresh'])
            UserSession.objects.create(
                user_id=refresh['user_id'],
                jti=refresh['jti'],
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
            )
        return response


class TrackedTokenRefreshView(TokenRefreshView):
    """Keeps UserSession.jti in sync as SimpleJWT rotates refresh tokens on each use."""

    def post(self, request, *args, **kwargs):
        old_jti = None
        try:
            old_jti = RefreshToken(request.data.get('refresh'))['jti']
        except Exception:
            pass

        response = super().post(request, *args, **kwargs)

        if response.status_code == 200 and old_jti:
            new_jti = RefreshToken(response.data['refresh'])['jti']
            UserSession.objects.filter(jti=old_jti).update(jti=new_jti)

        return response
