from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from .models import UserSession


def revoke_all_sessions(user):
    """Blacklist every refresh token the user holds and forget their sessions, logging them out everywhere."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)
    UserSession.objects.filter(user=user).delete()
