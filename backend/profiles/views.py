from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsFreelancer

from .counties import COUNTY_CHOICES
from .models import FreelancerProfile, PortfolioItem, Skill
from .serializers import (
    ClientProfileCompleteSerializer,
    FreelancerProfileCompleteSerializer,
    PortfolioItemSerializer,
    PublicProfileSerializer,
    SkillCreateSerializer,
    SkillSerializer,
    SubmitVerificationSerializer,
)


class SkillListView(generics.ListCreateAPIView):
    queryset = Skill.objects.all()

    throttle_scope = 'skill_create'

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_throttles(self):
        # Only creating skills is rate limited; listing them stays unthrottled.
        if self.request.method == 'POST':
            return [ScopedRateThrottle()]
        return []

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SkillCreateSerializer
        return SkillSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        skill = serializer.save()
        return Response(SkillSerializer(skill).data, status=status.HTTP_201_CREATED)


class ProfileCompleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    # JSON as well as forms: a form cannot send an empty skills list, so removing every skill needs JSON.
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request):
        user = request.user

        if user.role == User.Role.FREELANCER:
            profile = user.freelancer_profile
            serializer = FreelancerProfileCompleteSerializer(
                profile, data=request.data, partial=True, context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            if profile.bio:
                user.is_profile_complete = True
                user.save(update_fields=['is_profile_complete'])
            return Response(serializer.data)

        if user.role == User.Role.CLIENT:
            profile = user.client_profile
            serializer = ClientProfileCompleteSerializer(
                profile, data=request.data, partial=True, context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            user.is_profile_complete = True
            user.save(update_fields=['is_profile_complete'])
            return Response(serializer.data)

        return Response({'detail': 'Not applicable for this role.'}, status=status.HTTP_400_BAD_REQUEST)


class PortfolioItemListCreateView(generics.ListCreateAPIView):
    serializer_class = PortfolioItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsFreelancer]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return PortfolioItem.objects.filter(freelancer=self.request.user.freelancer_profile)

    def perform_create(self, serializer):
        serializer.save(freelancer=self.request.user.freelancer_profile)


class PortfolioItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PortfolioItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsFreelancer]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return PortfolioItem.objects.filter(freelancer=self.request.user.freelancer_profile)


class PublicProfileView(generics.RetrieveAPIView):
    queryset = User.objects.filter(is_active=True)
    serializer_class = PublicProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'user_id'


class SubmitVerificationView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFreelancer]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        profile = request.user.freelancer_profile
        serializer = SubmitVerificationSerializer(profile, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            verification_status=FreelancerProfile.VerificationStatus.PENDING, verification_submitted_at=timezone.now(),
        )
        # never echo id_number/id_document back — build the response by hand
        return Response({
            'detail': 'Verification submitted for review.',
            'verification_status': profile.verification_status,
        })


class CountyListView(APIView):
    """Read-only list of Kenya's counties, from profiles.counties (the one source of truth)."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response([{'value': name, 'label': label} for name, label in COUNTY_CHOICES])
