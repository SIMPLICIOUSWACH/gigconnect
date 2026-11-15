from rest_framework import serializers

from .models import REPLY_MAX_LENGTH, REVIEW_MAX_LENGTH, Review
from .service import client_name, window_closes_at, window_open


class ReviewWriteSerializer(serializers.Serializer):
    """What a client sends: 1 to 5 stars and, if they like, some words."""

    rating = serializers.IntegerField(
        min_value=1, max_value=5,
        error_messages={
            'required': 'Choose 1 to 5 stars.', 'min_value': 'Choose 1 to 5 stars.',
            'max_value': 'Choose 1 to 5 stars.', 'invalid': 'Choose 1 to 5 stars.',
        },
    )
    text = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=True, max_length=REVIEW_MAX_LENGTH, default='',
        error_messages={'max_length': f'Keep your review under {REVIEW_MAX_LENGTH} characters.'},
    )


class ReviewEditSerializer(ReviewWriteSerializer):
    rating = serializers.IntegerField(
        required=False, min_value=1, max_value=5,
        error_messages={
            'min_value': 'Choose 1 to 5 stars.', 'max_value': 'Choose 1 to 5 stars.', 'invalid': 'Choose 1 to 5 stars.',
        },
    )
    text = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=True, max_length=REVIEW_MAX_LENGTH,
        error_messages={'max_length': f'Keep your review under {REVIEW_MAX_LENGTH} characters.'},
    )


class ReplySerializer(serializers.Serializer):
    reply = serializers.CharField(
        trim_whitespace=True, max_length=REPLY_MAX_LENGTH,
        error_messages={
            'blank': 'Write a reply first.', 'required': 'Write a reply first.',
            'max_length': f'Keep your reply under {REPLY_MAX_LENGTH} characters.',
        },
    )


class PublicReviewSerializer(serializers.ModelSerializer):
    """What anyone signed in may see of a review. No ids of people, and nothing about moderation."""

    gig_title = serializers.CharField(source='gig.title', read_only=True)
    client_name = serializers.SerializerMethodField()
    edited = serializers.SerializerMethodField()
    reply = serializers.CharField(source='freelancer_reply', read_only=True)
    can_reply = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ['id', 'rating', 'text', 'gig_title', 'client_name', 'created_at', 'edited', 'reply', 'reply_at',
                  'can_reply']

    def get_client_name(self, obj):
        return client_name(obj)

    def get_edited(self, obj):
        return (obj.updated_at - obj.created_at).total_seconds() > 1

    def get_can_reply(self, obj):
        """True only for the freelancer who was rated, until they have replied."""
        request = self.context.get('request')
        return bool(request and request.user.pk == obj.freelancer_id and obj.reply_at is None)


class OwnReviewSerializer(serializers.ModelSerializer):
    """The client's own review of a gig, with whether they can still change it."""

    freelancer_name = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    closes_at = serializers.SerializerMethodField()
    removed = serializers.BooleanField(source='is_removed', read_only=True)
    reply = serializers.CharField(source='freelancer_reply', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'rating', 'text', 'freelancer_name', 'created_at', 'updated_at', 'reply', 'reply_at',
                  'can_edit', 'closes_at', 'removed', 'removed_reason']

    def get_freelancer_name(self, obj):
        return 'Deleted user' if obj.freelancer.deleted_at is not None else obj.freelancer.full_name

    def get_can_edit(self, obj):
        return window_open(obj.gig) and not obj.is_removed

    def get_closes_at(self, obj):
        return window_closes_at(obj.gig)
