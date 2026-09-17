from rest_framework.permissions import BasePermission


class IsOwnerClient(BasePermission):
    """Object-level check — the requesting user must be the client who posted the gig."""

    message = 'You do not own this gig.'

    def has_object_permission(self, request, view, obj):
        return obj.client_id == request.user.id
