import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from profiles.counties import COUNTY_CHOICES
from profiles.models import Skill


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Categories'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ModerationStatus(models.TextChoices):
    """Set by an admin, separately from a gig's or application's own status, so a restore puts it back as it was."""

    VISIBLE = 'visible', 'Visible'
    REMOVED = 'removed', 'Removed'


class Gig(models.Model):
    Moderation = ModerationStatus

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CLOSED = 'closed', 'Closed'

    # GigConnect is KES-only (see GigValidationMixin.validate in serializers.py for the actual
    # enforcement on create). The field stays a plain CharField rather than gaining DB-level
    # choices: that would be schema churn for a constraint Django doesn't enforce at the DB
    # layer anyway, and historical/imported rows (see the ML data pipeline) may legitimately
    # carry a converted-from value worth keeping visible rather than coercing to KES silently.
    CURRENCY_KES = 'KES'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='gigs')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='gigs')
    title = models.CharField(max_length=200)
    description = models.TextField()
    budget_min = models.DecimalField(max_digits=10, decimal_places=2)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default=CURRENCY_KES)
    deadline = models.DateField()
    # Last day to apply — distinct from `deadline` (project delivery date). Nullable at the
    # column level so it *can* be omitted on input, but save() always fills it in, so it's
    # functionally never null once persisted.
    application_deadline = models.DateField(null=True, blank=True)
    is_negotiable = models.BooleanField(default=True)
    county = models.CharField(max_length=40, choices=COUNTY_CHOICES, null=True, blank=True)
    is_remote = models.BooleanField(default=False)
    is_synthetic = models.BooleanField(default=False)
    # Extra rows seed_demo_conversations adds to the planted demo so it has chats to show. The recommender never
    # trains or evaluates on them, so the demo's model sees the same world with or without them.
    is_demo_extra = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    # When the status last changed, set by save(). A chat about a completed or closed gig turns read-only 30 days
    # after this (see messaging/rules.py).
    status_changed_at = models.DateTimeField(null=True, blank=True)
    skills = models.ManyToManyField(Skill, through='GigSkill', related_name='gigs')
    view_count = models.PositiveIntegerField(default=0)
    # A removed gig is hidden everywhere but its owner's My gigs, where it is read-only. See gigs/feed.py.
    moderation_status = models.CharField(
        max_length=10, choices=ModerationStatus.choices, default=ModerationStatus.VISIBLE
    )
    removed_reason = models.TextField(blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Stored, weighted full-text search vector (title=A, skills=B, description=C). Kept in
    # sync by signals (post_save for title/description, m2m_changed for skills) — see
    # gigs/signals.py. Never set this directly; it's derived data.
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Trigram GIN index — kept per the original proposal. Good for fuzzy/partial
            # matching on description alone, but can't do weighted multi-field ranking, which
            # is what `search_vector` below is for.
            GinIndex(fields=['description'], name='gig_description_gin', opclasses=['gin_trgm_ops']),
            GinIndex(fields=['search_vector'], name='gig_search_vector_gin'),
            # Covers the default public feed query: WHERE status='open' ORDER BY created_at DESC.
            models.Index(fields=['status', '-created_at'], name='gig_status_created_idx'),
            # Covers browsing/filtering by category within open gigs.
            models.Index(fields=['status', 'category'], name='gig_status_category_idx'),
            models.Index(fields=['deadline'], name='gig_deadline_idx'),
            models.Index(fields=['application_deadline'], name='gig_app_deadline_idx'),
            models.Index(fields=['budget_min'], name='gig_budget_min_idx'),
            models.Index(fields=['budget_max'], name='gig_budget_max_idx'),
        ]

    @classmethod
    def from_db(cls, db, field_names, values):
        gig = super().from_db(db, field_names, values)
        gig._loaded_status = gig.__dict__.get('status')
        return gig

    def save(self, *args, **kwargs):
        if self.application_deadline is None:
            self.application_deadline = self.deadline
        if self.status != getattr(self, '_loaded_status', None):
            self.status_changed_at = timezone.now()
            update_fields = kwargs.get('update_fields')
            if update_fields is not None and 'status' in update_fields:
                kwargs['update_fields'] = {*update_fields, 'status_changed_at'}
        super().save(*args, **kwargs)
        self._loaded_status = self.status

    def __str__(self):
        return self.title

    @property
    def is_removed(self):
        return self.moderation_status == ModerationStatus.REMOVED


class GigSkill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gig = models.ForeignKey(Gig, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['gig', 'skill'], name='unique_gig_skill'),
        ]

    def __str__(self):
        return f'{self.gig_id}:{self.skill_id}'


class GigInvite(models.Model):
    """
    A client asking a freelancer to apply to one of their open gigs. One per freelancer per gig. It sends a
    notification and nothing else: no chat opens (that still starts on hire), and the recommender never reads these.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gig = models.ForeignKey(Gig, on_delete=models.CASCADE, related_name='invites')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invites_sent')
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invites_received'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['gig', 'freelancer'], name='one_invite_per_freelancer_per_gig'),
        ]
        indexes = [
            # The daily limit counts a client's recent invites.
            models.Index(fields=['client', '-created_at'], name='invite_client_created_idx'),
        ]

    def __str__(self):
        return f'GigInvite<{self.gig_id} -> {self.freelancer_id}>'


class GigInteraction(models.Model):
    """One thing a visitor did with a gig. This is the training data for the collaborative filter."""

    class Type(models.TextChoices):
        VIEW = 'view', 'View'
        SEARCH_CLICK = 'search_click', 'Search click'
        SAVE = 'save', 'Save'
        APPLY = 'apply', 'Apply'  # written by the applications flow (Sprint 4)
        # Opening a gig from the "Recommended for You" list. Position is its place in that list.
        RECOMMENDATION_CLICK = 'recommendation_click', 'Recommendation click'
        # A freelancer's answer to "Is this gig relevant to you?" on a recommended gig (Sprint 6, for user acceptance
        # testing). One answer per freelancer and gig: a new answer replaces the old one. Position is the gig's place
        # in the list when it was rated. These never feed training (recommendations/platform.py leaves them out).
        RECOMMENDATION_RELEVANT = 'recommendation_relevant', 'Rated relevant'
        RECOMMENDATION_NOT_RELEVANT = 'recommendation_not_relevant', 'Rated not relevant'

    RELEVANCE_TYPES = (Type.RECOMMENDATION_RELEVANT, Type.RECOMMENDATION_NOT_RELEVANT)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Null for anonymous visitors, who are identified by session_key instead.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='gig_interactions'
    )
    session_key = models.CharField(max_length=40, blank=True)
    gig = models.ForeignKey(Gig, on_delete=models.CASCADE, related_name='interactions')
    type = models.CharField(max_length=30, choices=Type.choices)
    # The search text and the result's rank when this came from a search; null otherwise.
    query = models.TextField(null=True, blank=True)
    position = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_synthetic = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'gig'], name='interaction_user_gig_idx'),
            models.Index(fields=['type', 'created_at'], name='interaction_type_created_idx'),
        ]

    def __str__(self):
        return f'{self.type} {self.gig_id}'
