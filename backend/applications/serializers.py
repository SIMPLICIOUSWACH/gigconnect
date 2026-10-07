from rest_framework import serializers

from .models import COVER_LETTER_MAX_LENGTH, COVER_LETTER_MIN_LENGTH, Application, ApplicationStatusEvent
from .transitions import Actor, Status, allowed_next_statuses

STATUS_ORDER = [value for value, _ in Status.choices]


class ApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ['cover_letter', 'portfolio_link', 'proposed_rate']
        extra_kwargs = {
            'cover_letter': {
                'error_messages': {
                    'required': 'Please write a cover letter.',
                    'blank': 'Please write a cover letter.',
                    'min_length': f'Your cover letter needs at least {COVER_LETTER_MIN_LENGTH} characters.',
                    'max_length': f'Your cover letter can be at most {COVER_LETTER_MAX_LENGTH} characters.',
                },
            },
            'portfolio_link': {'error_messages': {'invalid': 'Enter a full web address, for example https://example.com.'}},
            'proposed_rate': {
                'error_messages': {
                    'min_value': 'The proposed rate must be more than zero.',
                    'invalid': 'Enter the proposed rate as a number in KES.',
                    'max_digits': 'That rate is too large.',
                    'max_whole_digits': 'That rate is too large.',
                },
            },
        }


class StatusEventSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationStatusEvent
        fields = ['id', 'from_status', 'to_status', 'changed_by_name', 'note', 'created_at']

    def get_changed_by_name(self, obj):
        return obj.changed_by.full_name if obj.changed_by_id else 'System'


class ApplicationListSerializer(serializers.ModelSerializer):
    """The light version used in lists: just enough to show a row and link to the gig."""

    gig_id = serializers.UUIDField(read_only=True)
    gig_title = serializers.CharField(source='gig.title', read_only=True)
    gig_status = serializers.CharField(source='gig.status', read_only=True)
    client_name = serializers.CharField(source='gig.client.full_name', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'gig_id', 'gig_title', 'gig_status', 'client_name', 'status', 'proposed_rate',
            'created_at', 'updated_at',
        ]


class ApplicationDetailSerializer(ApplicationListSerializer):
    applicant = serializers.SerializerMethodField()
    events = StatusEventSerializer(many=True, read_only=True)
    allowed_next_statuses = serializers.SerializerMethodField()

    class Meta(ApplicationListSerializer.Meta):
        fields = ApplicationListSerializer.Meta.fields + [
            'cover_letter', 'portfolio_link', 'applicant', 'events', 'allowed_next_statuses',
        ]

    def get_applicant(self, obj):
        user = obj.freelancer
        profile = getattr(user, 'freelancer_profile', None)
        return {
            'id': str(user.id),
            'full_name': user.full_name,
            'verification_status': profile.verification_status if profile else None,
            'verified': bool(profile and profile.verified),
            'skills': [{'id': str(s.id), 'name': s.name} for s in profile.skills.all()] if profile else [],
        }

    def get_allowed_next_statuses(self, obj):
        """What the person looking at this application may do to it, from the shared rules."""
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return []
        if request.user.id == obj.freelancer_id:
            actor = Actor.FREELANCER
        elif request.user.id == obj.gig.client_id:
            actor = Actor.CLIENT
        else:
            return []
        allowed = allowed_next_statuses(obj.status, actor)
        return [status for status in STATUS_ORDER if status in allowed]


class ApplicationFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Status.choices, required=False)
