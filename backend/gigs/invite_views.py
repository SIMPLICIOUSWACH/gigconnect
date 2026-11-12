"""
Reaching out from an open gig. All three are for the client who owns the gig.

    GET  /api/gigs/<id>/suggested-freelancers/        up to 6 freelancers the content model ranks best for the gig
    POST /api/gigs/<id>/invites/                      {"freelancer_id"}: invite them to apply
    GET  /api/freelancers/<id>/invitable-gigs/        my open gigs, and whether this freelancer was invited or applied

See invites.py for the rules.
"""

from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsClientRole

from .invites import InviteError, invitable_gigs, invite, invites_left, suggested_freelancers
from .models import Gig


def own_gig(request, gig_id):
    """Someone else's gig looks like it doesn't exist."""
    return get_object_or_404(Gig.objects.select_related('category').prefetch_related('skills'), pk=gig_id,
                             client=request.user)


class SuggestedFreelancersView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsClientRole]

    def get(self, request, gig_id):
        cards, availability = suggested_freelancers(own_gig(request, gig_id), request)
        return Response({'results': cards, 'suggestions': availability})


class InviteSerializer(serializers.Serializer):
    freelancer_id = serializers.UUIDField()


class GigInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsClientRole]

    def post(self, request, gig_id):
        gig = own_gig(request, gig_id)
        body = InviteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            row = invite(request.user, gig, body.validated_data['freelancer_id'])
        except InviteError as error:
            return Response({'detail': str(error)}, status=error.status)
        return Response(
            {
                'detail': f'{row.freelancer.full_name} was invited to apply.',
                'gig_id': str(gig.pk), 'freelancer_id': str(row.freelancer_id),
                'invites_left': invites_left(request.user),
            },
            status=status.HTTP_201_CREATED,
        )


class InvitableGigsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsClientRole]

    def get(self, request, user_id):
        return Response({
            'gigs': invitable_gigs(request.user, user_id),
            'invites_left': invites_left(request.user),
        })
