from django.urls import path

from .views import SkillListView

urlpatterns = [
    path('skills/', SkillListView.as_view(), name='skill-list'),
]
