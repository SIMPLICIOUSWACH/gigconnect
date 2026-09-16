from rest_framework import generics, permissions

from .models import Skill
from .serializers import SkillSerializer


class SkillListView(generics.ListAPIView):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [permissions.AllowAny]
