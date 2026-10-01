from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdminRole, IsFreelancer

from .models import FreelancerProfile, PortfolioItem, Skill
from .serializers import (
    AdminVerificationListSerializer,
    AdminVerificationUpdateSerializer,
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

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

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
    parser_classes = [MultiPartParser, FormParser]

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
        serializer.save(verification_status=FreelancerProfile.VerificationStatus.PENDING)
        # never echo id_number/id_document back — build the response by hand
        return Response({
            'detail': 'Verification submitted for review.',
            'verification_status': profile.verification_status,
        })


class AdminVerificationListView(generics.ListAPIView):
    serializer_class = AdminVerificationListSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        status_param = self.request.query_params.get('status', FreelancerProfile.VerificationStatus.PENDING)
        return FreelancerProfile.objects.filter(verification_status=status_param)


class AdminVerificationDetailView(generics.UpdateAPIView):
    queryset = FreelancerProfile.objects.all()
    serializer_class = AdminVerificationUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    http_method_names = ['patch']
