from rest_framework import serializers

from .models import ClientProfile, FreelancerProfile, PortfolioItem, Skill


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name', 'category']


class PortfolioItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioItem
        fields = ['id', 'title', 'description', 'link', 'image', 'created_at']
        read_only_fields = ['id', 'created_at']


class ClientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientProfile
        fields = ['company_name', 'industry', 'company_logo']


class ClientProfileCompleteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientProfile
        fields = ['company_logo']


class FreelancerProfileCompleteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FreelancerProfile
        fields = ['bio', 'profile_photo']


class FreelancerProfileSerializer(serializers.ModelSerializer):
    # id_number and id_document are intentionally omitted — never serialized out, per spec.
    skills = SkillSerializer(many=True, read_only=True)
    portfolio_items = PortfolioItemSerializer(many=True, read_only=True)
    verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = FreelancerProfile
        fields = [
            'bio', 'profile_photo', 'skills', 'portfolio_items',
            'verification_status', 'verified',
        ]
