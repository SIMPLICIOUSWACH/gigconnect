from django.urls import path

from .views import RecommendationsView, RelevanceView

urlpatterns = [
    path('recommendations/', RecommendationsView.as_view(), name='recommendations'),
    path('recommendations/<uuid:gig_id>/relevance/', RelevanceView.as_view(), name='recommendation-relevance'),
]
