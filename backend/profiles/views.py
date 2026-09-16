from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsFreelancer

from .models import PortfolioItem, Skill
from .serializers import (
    ClientProfileCompleteSerializer,
    FreelancerProfileCompleteSerializer,
    PortfolioItemSerializer,
    SkillSerializer,
)


class SkillListView(generics.ListAPIView):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [permissions.AllowAny]


class ProfileCompleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request):
        user = request.user

        if user.role == User.Role.FREELANCER:
            profile = user.freelancer_profile
            serializer = FreelancerProfileCompleteSerializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            if profile.bio:
                user.is_profile_complete = True
                user.save(update_fields=['is_profile_complete'])
            return Response(serializer.data)

        if user.role == User.Role.CLIENT:
            profile = user.client_profile
            serializer = ClientProfileCompleteSerializer(profile, data=request.data, partial=True)
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
