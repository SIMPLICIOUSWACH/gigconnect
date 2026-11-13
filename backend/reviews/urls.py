from django.urls import path

from .views import FreelancerReviewsView, GigReviewView, ReviewReplyView

urlpatterns = [
    path('gigs/<uuid:gig_id>/review/', GigReviewView.as_view(), name='gig-review'),
    path('reviews/<uuid:pk>/reply/', ReviewReplyView.as_view(), name='review-reply'),
    path('freelancers/<uuid:user_id>/reviews/', FreelancerReviewsView.as_view(), name='freelancer-reviews'),
]
