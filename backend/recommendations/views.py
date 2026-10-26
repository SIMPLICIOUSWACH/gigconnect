from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.permissions import IsEmailVerified, IsFreelancer
from gigs.models import Gig, GigInteraction
from gigs.pagination import GigPagination
from gigs.serializers import GigListSerializer

from . import registry
from .candidates import candidate_gigs
from .recommend import attach_gigs, recommend

NO_SKILLS = 'no_skills'


class RecommendationsView(APIView):
    """
    GET: gigs recommended for the signed-in freelancer, best first, paginated like the gig list.

    Each result has the gig card fields plus `score` (0 to 1, from the trained model for this freelancer
    and this gig), `match_reasons` (the skills they really share) and `source` ('content' or 'hybrid').

    This always answers 200 for a freelancer. When there is nothing honest to show, `available` is false or
    `results` is empty, and `reason` says why, so the page can show a plain empty state:

        reason "disabled"           recommendations are switched off
        reason "model_unavailable"  no trained model could be loaded
        reason "no_skills"          the freelancer has no skills or bio to compare gigs with
        reason null, no results     no gig the freelancer could apply to scores above zero

    A gig that scores exactly 0 shares nothing with the freelancer, so it is not recommended.
    """

    permission_classes = [IsAuthenticated, IsFreelancer, IsEmailVerified]

    def get(self, request):
        paginator = GigPagination()
        availability = registry.availability()
        if not availability.available:
            return Response(self._empty(paginator, request, available=False, reason=availability.reason))

        model = availability.model
        outcome = recommend(model, request.user, candidate_gigs(request.user))
        if not outcome.scorable:
            empty = self._empty(paginator, request, available=True, reason=NO_SKILLS, outcome=outcome, model=model)
            return Response(empty)

        worth_showing = [item for item in outcome.results if item.score > 0]
        page = attach_gigs(paginator.paginate_queryset(worth_showing, request, view=self))
        answers = relevance_answers(request.user, [item.gig_id for item in page])
        rows = [
            {
                **GigListSerializer(item.gig).data,
                'score': round(item.score, 4),
                'match_reasons': item.match_reasons,
                'source': item.source,
                'relevance': answers.get(item.gig_id),
            }
            for item in page
        ]
        response = paginator.get_paginated_response(rows)
        response.data.update(self._about(available=True, reason=None, outcome=outcome, model=model))
        return response

    def _about(self, available, reason, outcome=None, model=None):
        return {
            'available': available,
            'reason': reason,
            'cold_start': outcome.cold_start if outcome else None,
            'model': {
                'version': model.version.version,
                'trained_at': model.version.trained_at,
                'collaborative': model.collaborative is not None,
            } if model else None,
        }

    def _empty(self, paginator, request, available, reason, outcome=None, model=None):
        data = {
            'count': 0,
            'page': 1,
            'page_size': paginator.get_page_size(request),
            'total_pages': 0,
            'next': None,
            'previous': None,
            'results': [],
        }
        data.update(self._about(available=available, reason=reason, outcome=outcome, model=model))
        return data


RELEVANCE_NAMES = {
    GigInteraction.Type.RECOMMENDATION_RELEVANT: 'relevant',
    GigInteraction.Type.RECOMMENDATION_NOT_RELEVANT: 'not_relevant',
}


def relevance_answers(user, gig_ids):
    """{gig id: 'relevant' or 'not_relevant'}: this freelancer's current answer for each of these gigs, if any."""
    rows = GigInteraction.objects.filter(
        user=user, gig_id__in=gig_ids, type__in=GigInteraction.RELEVANCE_TYPES,
    ).values_list('gig_id', 'type')
    return {gig_id: RELEVANCE_NAMES[kind] for gig_id, kind in rows}


class RelevanceSerializer(serializers.Serializer):
    relevant = serializers.BooleanField()
    # The gig's place in the "Recommended for You" list when it was rated, so answers can be counted in the top 5
    # and top 10.
    position = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=10000)


class RelevanceView(APIView):
    """
    PUT: the signed-in freelancer's answer to "Is this gig relevant to you?" for a recommended gig, as
    {"relevant": true or false, "position": its place in the list}. A new answer replaces the old one, so the answer
    can be changed and each freelancer has at most one per gig.

    Stored as a recommendation_relevant or recommendation_not_relevant interaction. Neither feeds training. Only
    while recommendations are switched on.
    """

    permission_classes = [IsAuthenticated, IsFreelancer, IsEmailVerified]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'gig_interaction'

    def put(self, request, gig_id):
        if not settings.RECOMMENDATIONS_ENABLED:
            return Response({'detail': 'Recommendations are switched off.'}, status=status.HTTP_403_FORBIDDEN)
        gig = get_object_or_404(Gig, pk=gig_id)
        serializer = RelevanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        relevant = serializer.validated_data['relevant']
        kind = (
            GigInteraction.Type.RECOMMENDATION_RELEVANT if relevant else GigInteraction.Type.RECOMMENDATION_NOT_RELEVANT
        )
        with transaction.atomic():
            GigInteraction.objects.filter(
                user=request.user, gig=gig, type__in=GigInteraction.RELEVANCE_TYPES,
            ).delete()
            GigInteraction.objects.create(
                user=request.user, gig=gig, type=kind, position=serializer.validated_data.get('position'),
            )
        return Response({'gig': gig.id, 'relevance': RELEVANCE_NAMES[kind]})
