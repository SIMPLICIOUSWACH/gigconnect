from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from profiles.models import ClientProfile, Skill
from profiles.serializers import ClientProfileSerializer, FreelancerProfileSerializer

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    company_name = serializers.CharField(required=False, allow_blank=True, write_only=True)
    industry = serializers.ChoiceField(
        choices=ClientProfile.Industry.choices, required=False, allow_blank=True, write_only=True
    )
    skills = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(), many=True, required=False, write_only=True
    )

    class Meta:
        model = User
        fields = [
            'full_name', 'email', 'password', 'confirm_password', 'phone', 'role',
            'company_name', 'industry', 'skills',
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})

        role = attrs.get('role')
        client_fields_provided = [f for f in ('company_name', 'industry') if attrs.get(f)]

        if role == User.Role.FREELANCER:
            if client_fields_provided:
                raise serializers.ValidationError({
                    f: 'This field is only valid for Client registration.' for f in client_fields_provided
                })
            if not attrs.get('skills'):
                raise serializers.ValidationError({
                    'skills': 'At least one skill is required for Freelancer registration.'
                })
        elif role == User.Role.CLIENT:
            if attrs.get('skills'):
                raise serializers.ValidationError({
                    'skills': 'This field is only valid for Freelancer registration.'
                })

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        skills = validated_data.pop('skills', [])
        company_name = validated_data.pop('company_name', '')
        industry = validated_data.pop('industry', '')
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')

        user = User.objects.create_user(password=password, **validated_data)

        # profiles.signals auto-creates the matching profile row on User creation
        if user.role == User.Role.CLIENT:
            profile = user.client_profile
            profile.company_name = company_name
            profile.industry = industry
            profile.save()
        elif user.role == User.Role.FREELANCER:
            user.freelancer_profile.skills.set(skills)

        return user


class UserSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'phone', 'role',
            'is_email_verified', 'is_phone_verified', 'is_profile_complete',
            'created_at', 'profile',
        ]

    def get_profile(self, obj):
        if obj.role == User.Role.CLIENT:
            return ClientProfileSerializer(obj.client_profile).data
        if obj.role == User.Role.FREELANCER:
            return FreelancerProfileSerializer(obj.freelancer_profile).data
        return None
