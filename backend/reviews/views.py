"""
Reviews: a client's rating of the freelancer they hired, after the gig is completed.

    GET   /api/gigs/<id>/review/            the client's own review of their gig (404 if there is none yet)
    POST  /api/gigs/<id>/review/            {"rating": 1-5, "text"}: rate; within 14 days of completion, once
    PATCH /api/gigs/<id>/review/            change it, within the same 14 days
    POST  /api/reviews/<id>/reply/          {"reply"}: the freelancer's one public reply
    GET   /api/freelancers/<id>/reviews/    a freelancer's visible reviews, newest first, paginated
"""

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from gigs.models import Gig
from gigs.pagination import GigPagination

from .models import Review
from .serializers import (
    OwnReviewSerializer,
    PublicReviewSerializer,
    ReplySerializer,
    ReviewEditSerializer,
    ReviewWriteSerializer,
)
from .service import ReviewError, create_review, reply_to_review, update_review


def refused(error):
    return Response({'detail': str(error)}, status=status.HTTP_400_BAD_REQUEST)


class GigReviewView(APIView):
    """Only the gig's client gets anything here; for everyone else the gig looks like it doesn't exist."""

    permission_classes = [permissions.IsAuthenticated]

    def gig(self, request, gig_id):
        return get_object_or_404(Gig, pk=gig_id, client=request.user)

    def own(self, review, code=status.HTTP_200_OK):
        return Response(OwnReviewSerializer(review).data, status=code)

    def get(self, request, gig_id):
        review = get_object_or_404(Review.objects.select_related('gig', 'freelancer'), gig=self.gig(request, gig_id))
        return self.own(review)

    def post(self, request, gig_id):
        gig = self.gig(request, gig_id)
        body = ReviewWriteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            review = create_review(request.user, gig, **body.validated_data)
        except ReviewError as error:
            return refused(error)
        except IntegrityError:
            return refused('You have already rated this gig. You can edit your review instead.')
        return self.own(review, status.HTTP_201_CREATED)

    def patch(self, request, gig_id):
        gig = self.gig(request, gig_id)
        review = get_object_or_404(Review.objects.select_related('gig', 'freelancer'), gig=gig)
        body = ReviewEditSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            review = update_review(request.user, review, **body.validated_data)
        except ReviewError as error:
            return refused(error)
        return self.own(review)


class ReviewReplyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        review = get_object_or_404(
            Review.objects.select_related('gig', 'client', 'freelancer'), pk=pk, freelancer=request.user,
        )
        body = ReplySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            review = reply_to_review(request.user, review, body.validated_data['reply'])
        except ReviewError as error:
            return refused(error)
        return Response(PublicReviewSerializer(review, context={'request': request}).data)


class FreelancerReviewsView(generics.ListAPIView):
    """A freelancer's reviews. A deleted or deactivated freelancer has none to show: 404, like their profile."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PublicReviewSerializer
    pagination_class = GigPagination

    def get_queryset(self):
        freelancer = get_object_or_404(
            User, pk=self.kwargs['user_id'], role=User.Role.FREELANCER, is_active=True, deleted_at__isnull=True,
        )
        return (
            Review.objects.filter(freelancer=freelancer, moderation_status=Review.Moderation.VISIBLE)
            .select_related('gig', 'client').order_by('-created_at', '-id')
        )
