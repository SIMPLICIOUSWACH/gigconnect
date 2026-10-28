from rest_framework import serializers

from . import skills as skill_names
from .models import ClientProfile, FreelancerProfile, PortfolioItem, Skill


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name', 'category']


class SkillCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name', 'category']
        # No unique validator on name: posting an existing skill (or an alias of one) is a
        # get-or-create that returns the canonical skill, not an error.
        extra_kwargs = {
            'name': {'validators': []},
            'category': {'required': False, 'allow_blank': True},
        }

    def validate_name(self, value):
        error = skill_names.validation_error(value)
        if error:
            raise serializers.ValidationError(error)
        return skill_names.display_name(value)

    def create(self, validated_data):
        name = validated_data['name']
        # Resolves case/spacing variants and aliases (ReactJS -> React) to the existing skill.
        existing = skill_names.find_skill(name)
        if existing:
            return existing
        category = (validated_data.get('category') or 'Other').strip() or 'Other'
        return Skill.objects.create(name=name, category=category)


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
    """Used both by the Part 4 profile-completion step and the Settings > Company Profile page."""

    class Meta:
        model = ClientProfile
        fields = ['company_name', 'industry', 'company_logo']


class FreelancerProfileCompleteSerializer(serializers.ModelSerializer):
    """Used both by the Part 4 profile-completion step and the Settings > Profile & Portfolio page."""

    skills = serializers.PrimaryKeyRelatedField(queryset=Skill.objects.all(), many=True, required=False)

    class Meta:
        model = FreelancerProfile
        fields = [
            'bio', 'county', 'profile_photo', 'skills',
            'headline', 'starting_price', 'is_available', 'profile_colour',
        ]

    def validate_county(self, value):
        return value or None

    def validate_headline(self, value):
        return value.strip()


class FreelancerProfileSerializer(serializers.ModelSerializer):
    # id_number and id_document are intentionally omitted — never serialized out, per spec.
    skills = SkillSerializer(many=True, read_only=True)
    portfolio_items = PortfolioItemSerializer(many=True, read_only=True)
    verified = serializers.BooleanField(read_only=True)
    gigs_completed = serializers.SerializerMethodField()
    member_since = serializers.DateTimeField(source='user.created_at', read_only=True)

    class Meta:
        model = FreelancerProfile
        fields = [
            'headline', 'bio', 'county', 'profile_photo', 'skills', 'portfolio_items',
            'starting_price', 'is_available', 'profile_colour',
            'verification_status', 'verified', 'gigs_completed', 'member_since',
        ]

    def get_gigs_completed(self, obj):
        # Gigs the freelancer was hired for and the client then marked completed.
        from applications.models import Application
        from gigs.models import Gig

        return Application.objects.filter(
            freelancer_id=obj.user_id, status=Application.Status.HIRED, gig__status=Gig.Status.COMPLETED
        ).count()


class PublicProfileSerializer(serializers.Serializer):
    """Public-safe view of a user's profile — no email, phone, or verification flags."""

    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)
    profile = serializers.SerializerMethodField()

    def get_profile(self, obj):
        from accounts.models import User

        if obj.role == User.Role.CLIENT:
            return ClientProfileSerializer(obj.client_profile, context=self.context).data
        if obj.role == User.Role.FREELANCER:
            return FreelancerProfileSerializer(obj.freelancer_profile, context=self.context).data
        return None


class SubmitVerificationSerializer(serializers.ModelSerializer):
    id_number = serializers.CharField(required=True)
    id_document = serializers.FileField(required=True)

    class Meta:
        model = FreelancerProfile
        fields = ['id_number', 'id_document']


class AdminVerificationListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = FreelancerProfile
        fields = ['id', 'email', 'full_name', 'verification_status']


class AdminVerificationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FreelancerProfile
        fields = ['id', 'verification_status']
        read_only_fields = ['id']

    def validate_verification_status(self, value):
        allowed = (FreelancerProfile.VerificationStatus.VERIFIED, FreelancerProfile.VerificationStatus.REJECTED)
        if value not in allowed:
            raise serializers.ValidationError('Status must be either "verified" or "rejected".')
        return value
