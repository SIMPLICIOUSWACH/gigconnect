"""
Reviews, for admins: every review, and removing or restoring one. A removed review isn't shown and doesn't count
towards the freelancer's rating. Both people are told, and each change is written to the audit log.

    GET  /api/admin/reviews/?moderation=visible|removed&rating=1-5&id=&freelancer=&client=
    POST /api/admin/reviews/<id>/remove/    {"reason"} (required)
    POST /api/admin/reviews/<id>/restore/   {"reason"} (optional)
"""

from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response

from reviews.models import Review

from . import moderation
from .serializers import AdminReviewSerializer
from .views import AdminListView, AdminView, FilterSerializer, optional, reason_from, run_action


def reviews_with_people():
    return Review.objects.select_related('gig', 'client', 'freelancer')


class ReviewListView(AdminListView):
    serializer_class = AdminReviewSerializer

    def get_queryset(self):
        params = FilterSerializer(
            self,
            id=optional(serializers.UUIDField),
            freelancer=optional(serializers.UUIDField),
            client=optional(serializers.UUIDField),
            rating=optional(serializers.IntegerField, min_value=1, max_value=5),
            moderation=optional(serializers.ChoiceField, choices=Review.Moderation.values),
        ).values()
        reviews = reviews_with_people().order_by('-created_at')
        if 'id' in params:
            reviews = reviews.filter(pk=params['id'])
        if 'freelancer' in params:
            reviews = reviews.filter(freelancer_id=params['freelancer'])
        if 'client' in params:
            reviews = reviews.filter(client_id=params['client'])
        if 'rating' in params:
            reviews = reviews.filter(rating=params['rating'])
        if 'moderation' in params:
            reviews = reviews.filter(moderation_status=params['moderation'])
            if params['moderation'] == Review.Moderation.REMOVED:
                reviews = reviews.order_by('-removed_at')
        return reviews


class RemoveReviewView(AdminView):
    action = staticmethod(moderation.remove_review)

    def post(self, request, pk):
        review = get_object_or_404(reviews_with_people(), pk=pk)
        run_action(self.action, request.user, review, reason=reason_from(request))
        review.refresh_from_db()
        return Response(AdminReviewSerializer(review).data)


class RestoreReviewView(RemoveReviewView):
    action = staticmethod(moderation.restore_review)
