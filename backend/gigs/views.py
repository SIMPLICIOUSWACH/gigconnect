from datetime import date

from django.db.models import F
from rest_framework import generics, permissions
from rest_framework import status as http_status
from rest_framework.response import Response

from accounts.permissions import IsClientRole, IsEmailVerified

from .filters import GigFilterSerializer, apply_gig_filters
from .models import Category, Gig
from .pagination import GigPagination
from .permissions import IsOwnerClient
from .serializers import (
    CategorySerializer,
    GigCreateSerializer,
    GigDetailSerializer,
    GigListSerializer,
    GigStatusUpdateSerializer,
    GigUpdateSerializer,
)


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class GigListCreateView(generics.ListCreateAPIView):
    pagination_class = GigPagination

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), IsClientRole(), IsEmailVerified()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return GigCreateSerializer
        return GigListSerializer

    def get_queryset(self):
        # Public feed: open gigs only, and never anything past its application deadline —
        # those are still reachable directly by ID (see GigDetailView) but shouldn't show up
        # here. select_related/prefetch_related avoid N+1s across client/category/skills.
        return (
            Gig.objects.filter(status=Gig.Status.OPEN, application_deadline__gte=date.today())
            .select_related('client', 'client__client_profile', 'category')
            .prefetch_related('skills')
        )

    def list(self, request, *args, **kwargs):
        filters = GigFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)

        queryset = apply_gig_filters(self.get_queryset(), filters.validated_data)

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gig = serializer.save()
        detail = GigDetailSerializer(gig, context=self.get_serializer_context())
        return Response(detail.data, status=http_status.HTTP_201_CREATED)


class MyGigsView(generics.ListAPIView):
    serializer_class = GigListSerializer
    permission_classes = [permissions.IsAuthenticated, IsClientRole]

    def get_queryset(self):
        return (
            Gig.objects.filter(client=self.request.user)
            .select_related('client', 'client__client_profile', 'category')
            .prefetch_related('skills')
        )


class GigDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Gig.objects.all().select_related(
        'client', 'client__client_profile', 'category'
    ).prefetch_related('skills')
    http_method_names = ['get', 'put', 'delete']

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsClientRole(), IsOwnerClient()]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return GigDetailSerializer
        return GigUpdateSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        Gig.objects.filter(pk=instance.pk).update(view_count=F('view_count') + 1)
        instance.refresh_from_db(fields=['view_count'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        gig = serializer.save()
        return Response(GigDetailSerializer(gig, context=self.get_serializer_context()).data)


class GigStatusUpdateView(generics.UpdateAPIView):
    queryset = Gig.objects.all()
    serializer_class = GigStatusUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsClientRole, IsOwnerClient]
    http_method_names = ['patch']

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        gig = serializer.save()
        return Response(GigDetailSerializer(gig, context=self.get_serializer_context()).data)
