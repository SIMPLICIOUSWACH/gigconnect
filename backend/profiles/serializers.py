from rest_framework import serializers

from .models import ClientProfile, FreelancerProfile, PortfolioItem, Skill


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name', 'category']


class SkillCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name', 'category']
        extra_kwargs = {'category': {'required': False, 'allow_blank': True}}

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Skill name cannot be blank.')
        return value

    def create(self, validated_data):
        name = validated_data['name']
        category = (validated_data.get('category') or 'Other').strip() or 'Other'
        existing = Skill.objects.filter(name__iexact=name).first()
        if existing:
            return existing
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
        fields = ['bio', 'profile_photo', 'skills']


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
