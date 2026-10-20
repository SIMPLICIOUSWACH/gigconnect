from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsEmailVerified, IsFreelancer
from gigs.pagination import GigPagination
from gigs.serializers import GigListSerializer

from . import registry
from .candidates import candidate_gigs
from .recommend import recommend

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
        candidates = candidate_gigs(request.user).select_related('client')
        outcome = recommend(model, request.user, candidates)
        if not outcome.scorable:
            empty = self._empty(paginator, request, available=True, reason=NO_SKILLS, outcome=outcome, model=model)
            return Response(empty)

        worth_showing = [item for item in outcome.results if item.score > 0]
        page = paginator.paginate_queryset(worth_showing, request, view=self)
        rows = [
            {
                **GigListSerializer(item.gig).data,
                'score': round(item.score, 4),
                'match_reasons': item.match_reasons,
                'source': item.source,
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
