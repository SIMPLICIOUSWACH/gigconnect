from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

SUSPENDED_MESSAGE = 'This account is suspended. Check your email for the reason.'


def user_can_log_in(user):
    """SIMPLE_JWT's USER_AUTHENTICATION_RULE: used when logging in and when refreshing a token."""
    return user is not None and user.is_active and not user.is_suspended


class ActiveAccountJWTAuthentication(JWTAuthentication):
    """Rejects a suspended user's access tokens at once, rather than when they expire."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user.is_suspended:
            raise AuthenticationFailed(SUSPENDED_MESSAGE, code='account_suspended')
        return user
