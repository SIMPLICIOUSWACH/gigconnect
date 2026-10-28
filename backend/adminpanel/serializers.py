from rest_framework import serializers

from accounts.models import User
from applications.models import Application
from gigs.models import Gig
from profiles.models import FreelancerProfile

from .models import AdminAction


class ReasonSerializer(serializers.Serializer):
    """The body of every admin action. Whether a reason is required is checked in moderation.py."""

    reason = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True, default='')


class PersonSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField()


def account_state(user):
    """active, suspended or deleted. A deleted account keeps its row (see usersettings DeleteAccountView)."""
    if user.deleted_at is not None:
        return 'deleted'
    return user.account_status


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class AdminUserListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    verification_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'role', 'status', 'verification_status', 'is_email_verified',
            'is_synthetic', 'created_at',
        ]

    def get_status(self, obj):
        return account_state(obj)

    def get_verification_status(self, obj):
        """The freelancer's ID check. Clients have none."""
        profile = getattr(obj, 'freelancer_profile', None) if obj.role == User.Role.FREELANCER else None
        return profile.verification_status if profile else None


class AdminUserDetailSerializer(AdminUserListSerializer):
    profile = serializers.SerializerMethodField()

    class Meta(AdminUserListSerializer.Meta):
        fields = AdminUserListSerializer.Meta.fields + [
            'phone', 'is_phone_verified', 'suspended_reason', 'suspended_at', 'profile',
        ]

    def get_profile(self, obj):
        if obj.role == User.Role.FREELANCER and hasattr(obj, 'freelancer_profile'):
            profile = obj.freelancer_profile
            return {
                'headline': profile.headline,
                'county': profile.county,
                'bio': profile.bio,
                'starting_price': profile.starting_price,
                'skills': [skill.name for skill in profile.skills.all()],
            }
        if obj.role == User.Role.CLIENT and hasattr(obj, 'client_profile'):
            profile = obj.client_profile
            return {
                'company_name': profile.company_name,
                'industry': profile.get_industry_display() if profile.industry else '',
            }
        return None


# ---------------------------------------------------------------------------
# Gigs and applications
# ---------------------------------------------------------------------------

class AdminGigListSerializer(serializers.ModelSerializer):
    client = PersonSerializer(read_only=True)
    client_status = serializers.CharField(source='client.account_status', read_only=True)
    category = serializers.CharField(source='category.name', read_only=True)
    application_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Gig
        fields = [
            'id', 'title', 'client', 'client_status', 'category', 'status', 'moderation_status', 'removed_reason',
            'removed_at', 'budget_min', 'budget_max', 'currency', 'is_synthetic', 'application_count', 'created_at',
        ]


class AdminGigDetailSerializer(AdminGigListSerializer):
    skills = serializers.SerializerMethodField()

    class Meta(AdminGigListSerializer.Meta):
        fields = AdminGigListSerializer.Meta.fields + [
            'description', 'skills', 'deadline', 'application_deadline', 'is_negotiable', 'county', 'is_remote',
        ]

    def get_skills(self, obj):
        return [skill.name for skill in obj.skills.all()]


class AdminApplicationSerializer(serializers.ModelSerializer):
    gig = serializers.SerializerMethodField()
    freelancer = PersonSerializer(read_only=True)
    client = PersonSerializer(source='gig.client', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'gig', 'freelancer', 'client', 'status', 'moderation_status', 'removed_reason', 'removed_at',
            'cover_letter', 'portfolio_link', 'proposed_rate', 'is_synthetic', 'created_at',
        ]

    def get_gig(self, obj):
        return {'id': str(obj.gig_id), 'title': obj.gig.title, 'moderation_status': obj.gig.moderation_status}


# ---------------------------------------------------------------------------
# Verifications
# ---------------------------------------------------------------------------

class AdminVerificationSerializer(serializers.ModelSerializer):
    """
    A freelancer's ID submission, for admins only. The ID number is shown here so it can be checked against the
    document; no other response ever includes it. The document itself is fetched from its own admin-only endpoint.
    """

    user = PersonSerializer(read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    has_document = serializers.SerializerMethodField()

    class Meta:
        model = FreelancerProfile
        fields = [
            'id', 'user', 'email', 'verification_status', 'verification_submitted_at', 'id_number', 'has_document',
        ]

    def get_has_document(self, obj):
        return bool(obj.id_document)


class VerificationDecisionSerializer(ReasonSerializer):
    verification_status = serializers.ChoiceField(
        choices=[FreelancerProfile.VerificationStatus.VERIFIED, FreelancerProfile.VerificationStatus.REJECTED],
        error_messages={'invalid_choice': 'Status must be either "verified" or "rejected".'},
    )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class AdminActionSerializer(serializers.ModelSerializer):
    admin = PersonSerializer(read_only=True, allow_null=True)
    action_label = serializers.CharField(source='get_action_display', read_only=True)
    target_label = serializers.SerializerMethodField()

    class Meta:
        model = AdminAction
        fields = [
            'id', 'admin', 'action', 'action_label', 'target_type', 'target_id', 'target_label', 'reason',
            'created_at',
        ]

    def get_target_label(self, obj):
        """The target's name or title, from the lookup the view builds for the whole page."""
        return self.context.get('target_labels', {}).get((obj.target_type, obj.target_id), '')


def target_labels(actions):
    """{(target_type, target_id): name or title} for a page of AdminActions, in one query per target type."""
    wanted = {}
    for action in actions:
        wanted.setdefault(action.target_type, set()).add(action.target_id)
    labels = {}
    Target = AdminAction.TargetType
    if Target.USER in wanted:
        for pk, name in User.objects.filter(pk__in=wanted[Target.USER]).values_list('pk', 'full_name'):
            labels[(Target.USER, pk)] = name
    if Target.GIG in wanted:
        for pk, title in Gig.objects.filter(pk__in=wanted[Target.GIG]).values_list('pk', 'title'):
            labels[(Target.GIG, pk)] = title
    if Target.APPLICATION in wanted:
        rows = Application.objects.filter(pk__in=wanted[Target.APPLICATION]).values_list(
            'pk', 'freelancer__full_name', 'gig__title',
        )
        for pk, name, title in rows:
            labels[(Target.APPLICATION, pk)] = f'{name} on "{title}"'
    return labels
