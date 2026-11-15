"""
Find freelancers, for clients and admins.

    GET /api/freelancers/?q=&skills=&county=&remote=&verified=&available=&min_rating=&sort=&page=
        sort: best_match (default), rating, completed, newest. 12 per page.

Throttled, and without a keyword or a filter the list stops at page 50. See search.py for who appears and what a card
contains.
"""

from rest_framework import permissions, status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import User
from gigs.pagination import GigPagination

from .search import MAX_UNFILTERED_PAGES, PAGE_SIZE, FreelancerFilterSerializer, card, search


class IsClientOrAdmin(BasePermission):
    """Freelancers don't search for other freelancers."""

    message = 'Only clients can search for freelancers.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in (User.Role.CLIENT, User.Role.ADMIN))


class FreelancerPagination(GigPagination):
    page_size = PAGE_SIZE
    max_page_size = PAGE_SIZE


class FreelancerSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsClientOrAdmin]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'freelancer_search'

    def get(self, request):
        filters = FreelancerFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)

        try:
            page_number = int(request.query_params.get('page', 1))
        except ValueError:
            page_number = 1
        if page_number > MAX_UNFILTERED_PAGES and not filters.narrowed():
            return Response(
                {'detail': 'Add a search or a filter to see more freelancers.', 'code': 'narrow_your_search'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paginator = FreelancerPagination()
        page = paginator.paginate_queryset(search(filters.validated_data), request, view=self)
        return paginator.get_paginated_response([card(profile, request) for profile in page])
