from datetime import date

from rest_framework import serializers

from profiles.models import Skill
from profiles.serializers import SkillSerializer

from .models import Category, Gig, GigInteraction


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description']


class GigListSerializer(serializers.ModelSerializer):
    client_id = serializers.UUIDField(source='client.id', read_only=True)
    client_name = serializers.CharField(source='client.full_name', read_only=True)
    category = CategorySerializer(read_only=True)
    skills = SkillSerializer(many=True, read_only=True)

    class Meta:
        model = Gig
        fields = [
            'id', 'title', 'client_id', 'client_name', 'category',
            'budget_min', 'budget_max', 'currency', 'deadline', 'application_deadline',
            'is_negotiable', 'county', 'is_remote', 'status', 'skills', 'created_at',
        ]


class MyGigListSerializer(GigListSerializer):
    """A client's own gigs. The counts come from annotations set in MyGigsView."""

    application_count = serializers.IntegerField(read_only=True)
    pending_application_count = serializers.IntegerField(read_only=True)

    class Meta(GigListSerializer.Meta):
        fields = GigListSerializer.Meta.fields + ['application_count', 'pending_application_count']


class GigClientSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    company_name = serializers.SerializerMethodField()

    # No `verified` field here — Sprint 1 only built identity verification for
    # Freelancers, ClientProfile has no equivalent field, so it isn't faked here.
    def get_company_name(self, obj):
        return getattr(obj, 'client_profile', None) and obj.client_profile.company_name


class GigDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    client = GigClientSummarySerializer(read_only=True)
    my_application = serializers.SerializerMethodField()

    def get_my_application(self, obj):
        """The signed-in freelancer's own application to this gig, so the page can say "Applied"."""
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated or user.role != user.Role.FREELANCER:
            return None
        application = obj.applications.filter(freelancer=user).only('id', 'status').first()
        if application is None:
            return None
        return {'id': str(application.id), 'status': application.status}

    class Meta:
        model = Gig
        fields = [
            'id', 'title', 'description', 'client', 'category',
            'budget_min', 'budget_max', 'currency', 'deadline', 'application_deadline',
            'is_negotiable', 'county', 'is_remote', 'status', 'skills', 'view_count', 'created_at', 'updated_at',
            'my_application',
        ]


class GigValidationMixin:
    def validate(self, attrs):
        currency = attrs.get('currency')
        if currency is not None and currency != Gig.CURRENCY_KES:
            raise serializers.ValidationError(
                {'currency': 'GigConnect only supports KES gigs at this time.'}
            )

        budget_min = attrs.get('budget_min', getattr(self.instance, 'budget_min', None))
        budget_max = attrs.get('budget_max', getattr(self.instance, 'budget_max', None))
        if budget_min is not None and budget_max is not None and budget_max < budget_min:
            raise serializers.ValidationError(
                {'budget_max': 'Budget max must be greater than or equal to budget min.'}
            )

        deadline = attrs.get('deadline')
        if deadline is not None and deadline <= date.today():
            raise serializers.ValidationError({'deadline': 'Deadline must be in the future.'})

        application_deadline = attrs.get('application_deadline')
        if application_deadline is not None:
            if application_deadline <= date.today():
                raise serializers.ValidationError(
                    {'application_deadline': 'Application deadline must be in the future.'}
                )
            effective_deadline = deadline if deadline is not None else getattr(self.instance, 'deadline', None)
            if effective_deadline is not None and application_deadline > effective_deadline:
                raise serializers.ValidationError(
                    {'application_deadline': 'Application deadline cannot be after the project deadline.'}
                )

        return attrs


class GigCreateSerializer(GigValidationMixin, serializers.ModelSerializer):
    skills = serializers.PrimaryKeyRelatedField(queryset=Skill.objects.all(), many=True)

    class Meta:
        model = Gig
        fields = [
            'id', 'title', 'description', 'category',
            'budget_min', 'budget_max', 'currency', 'deadline', 'application_deadline',
            'is_negotiable', 'county', 'is_remote', 'skills',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'application_deadline': {'required': False},
            'is_negotiable': {'required': False},
        }

    def create(self, validated_data):
        skills = validated_data.pop('skills')
        request = self.context['request']
        gig = Gig.objects.create(client=request.user, **validated_data)
        gig.skills.set(skills)
        return gig


class GigUpdateSerializer(GigValidationMixin, serializers.ModelSerializer):
    skills = serializers.PrimaryKeyRelatedField(queryset=Skill.objects.all(), many=True)

    class Meta:
        model = Gig
        fields = [
            'title', 'description', 'category', 'budget_min', 'budget_max', 'deadline',
            'application_deadline', 'is_negotiable', 'county', 'is_remote', 'skills',
        ]
        extra_kwargs = {
            'application_deadline': {'required': False},
            'is_negotiable': {'required': False},
        }

    def validate(self, attrs):
        if self.instance.status != Gig.Status.OPEN:
            raise serializers.ValidationError(
                'This gig can no longer be edited because it is not open.'
            )
        return super().validate(attrs)

    def update(self, instance, validated_data):
        skills = validated_data.pop('skills', None)
        instance = super().update(instance, validated_data)
        if skills is not None:
            instance.skills.set(skills)
        return instance


ALLOWED_STATUS_TRANSITIONS = {
    Gig.Status.OPEN: {Gig.Status.IN_PROGRESS, Gig.Status.CLOSED},
    Gig.Status.IN_PROGRESS: {Gig.Status.COMPLETED, Gig.Status.CLOSED},
    Gig.Status.COMPLETED: set(),
    Gig.Status.CLOSED: set(),
}


class GigStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gig
        fields = ['status']

    def validate_status(self, value):
        current = self.instance.status
        if value not in ALLOWED_STATUS_TRANSITIONS.get(current, set()):
            raise serializers.ValidationError(f'Cannot change status from "{current}" to "{value}".')
        return value


class GigInteractionCreateSerializer(serializers.Serializer):
    """Body of POST /api/gigs/<id>/interactions/. Only search_click can be posted by the client:
    views are logged by the server (so they can't be inflated) and save/apply have their own flows."""

    type = serializers.ChoiceField(choices=[GigInteraction.Type.SEARCH_CLICK])
    query = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=200)
    position = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=10000)

