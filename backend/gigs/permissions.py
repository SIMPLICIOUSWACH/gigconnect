from rest_framework.permissions import BasePermission


class IsOwnerClient(BasePermission):
    """Object-level check — the requesting user must be the client who posted the gig."""

    message = 'You do not own this gig.'

    def has_object_permission(self, request, view, obj):
        return obj.client_id == request.user.id


class GigNotRemoved(BasePermission):
    """A gig an admin removed stays visible to its owner but can't be changed."""

    message = 'An administrator removed this gig, so it can no longer be changed.'

    def has_object_permission(self, request, view, obj):
        return not obj.is_removed
