from rest_framework.permissions import BasePermission


class IsEmailVerified(BasePermission):
    """Blocks actions (e.g. posting/applying to gigs) until the user has verified their email."""

    message = 'You must verify your email before performing this action.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_email_verified)
