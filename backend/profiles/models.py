import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from .counties import COUNTY_CHOICES
from .skills import display_name, match_key
from .storage import PrivateStorage


class Skill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # The display name, trimmed and with whitespace collapsed on save.
    name = models.CharField(max_length=100, unique=True)
    # Case-folded copy of `name`, maintained by save(); this is what matching uses.
    normalized_name = models.CharField(max_length=100, db_index=True, editable=False, blank=True, default='')
    category = models.CharField(max_length=100)

    class Meta:
        ordering = ['category', 'name']

    def save(self, *args, **kwargs):
        self.name = display_name(self.name)
        self.normalized_name = match_key(self.name)
        if 'update_fields' in kwargs and kwargs['update_fields'] is not None:
            kwargs['update_fields'] = {*kwargs['update_fields'], 'name', 'normalized_name'}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class SkillAlias(models.Model):
    """An alternative spelling (ReactJS, JS, MS Excel) that resolves to a canonical Skill."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    alias = models.CharField(max_length=100)
    normalized_alias = models.CharField(max_length=100, unique=True, editable=False)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='aliases')

    class Meta:
        ordering = ['alias']
        verbose_name_plural = 'Skill aliases'

    def save(self, *args, **kwargs):
        self.alias = display_name(self.alias)
        self.normalized_alias = match_key(self.alias)
        if 'update_fields' in kwargs and kwargs['update_fields'] is not None:
            kwargs['update_fields'] = {*kwargs['update_fields'], 'alias', 'normalized_alias'}
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.alias} -> {self.skill.name}'


class ClientProfile(models.Model):
    class Industry(models.TextChoices):
        TECHNOLOGY = 'technology', 'Technology'
        RETAIL = 'retail', 'Retail'
        AGRICULTURE = 'agriculture', 'Agriculture'
        CONSTRUCTION = 'construction', 'Construction'
        HOSPITALITY = 'hospitality', 'Hospitality'
        FINANCE = 'finance', 'Finance'
        EDUCATION = 'education', 'Education'
        HEALTHCARE = 'healthcare', 'Healthcare'
        OTHER = 'other', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='client_profile'
    )
    company_name = models.CharField(max_length=255, blank=True)
    industry = models.CharField(max_length=30, choices=Industry.choices, blank=True)
    company_logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)

    def __str__(self):
        return f'ClientProfile<{self.user.email}>'


class FreelancerProfile(models.Model):
    class VerificationStatus(models.TextChoices):
        UNVERIFIED = 'unverified', 'Unverified'
        PENDING = 'pending', 'Pending'
        VERIFIED = 'verified', 'Verified'
        REJECTED = 'rejected', 'Rejected'

    # The colour of the freelancer's avatar and profile header.
    class Colour(models.TextChoices):
        TEAL = 'teal', 'Teal'
        CORAL = 'coral', 'Coral'
        SUN = 'sun', 'Sunflower'
        VIOLET = 'violet', 'Violet'
        ROSE = 'rose', 'Rose'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='freelancer_profile'
    )
    skills = models.ManyToManyField(Skill, related_name='freelancers', blank=True)
    headline = models.CharField(max_length=120, blank=True)
    bio = models.CharField(max_length=300, blank=True)
    # In KES. Empty means "on request".
    starting_price = models.PositiveIntegerField(null=True, blank=True)
    is_available = models.BooleanField(default=True)
    # Happy to work for clients anywhere, not only in their own county.
    open_to_remote = models.BooleanField(default=True)
    # "Show my profile in Find freelancers". Off hides the profile from the client search and from suggestions; it
    # still opens from a link, and clients still see it on the freelancer's applications.
    search_visible = models.BooleanField(default=True)
    # Name, headline, skills and bio, for the client search. Kept up to date by profiles/signals.py.
    search_vector = SearchVectorField(null=True, editable=False)
    profile_colour = models.CharField(max_length=10, choices=Colour.choices, default=Colour.TEAL)
    county = models.CharField(max_length=40, choices=COUNTY_CHOICES, null=True, blank=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    # The average and number of this freelancer's visible reviews, kept up to date by reviews/service.py whenever a
    # review is written, edited, removed or restored. No reviews: rating_avg is empty, shown as "New", never as 0.
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rating_count = models.PositiveIntegerField(default=0)
    # write-only in every serializer — never include in a response, even to the owner
    id_number = models.CharField(max_length=20, blank=True)
    # In private storage: no URL reaches it. Admins read it through /api/admin/verifications/<id>/document/.
    id_document = models.FileField(upload_to='id_documents/', storage=PrivateStorage(), blank=True, null=True)
    verification_status = models.CharField(
        max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.UNVERIFIED
    )
    # When both parts were in and the check joined the admin queue, so admins can work through the oldest first.
    verification_submitted_at = models.DateTimeField(null=True, blank=True)

    # The live selfie, in the same private storage as the ID. Only admins can read it. See profiles/selfie.py.
    selfie = models.FileField(upload_to='selfies/', storage=PrivateStorage(), blank=True, null=True)
    # The challenge the person was shown, and when it was issued.
    selfie_challenge = models.CharField(max_length=200, blank=True)
    selfie_challenge_issued_at = models.DateTimeField(null=True, blank=True)
    # When they agreed that GigConnect may use the photo to confirm their identity.
    selfie_consent_at = models.DateTimeField(null=True, blank=True)
    selfie_submitted_at = models.DateTimeField(null=True, blank=True)
    # Set when an admin rejects a check: the part or parts to send again. The rest is kept.
    needs_new_id = models.BooleanField(default=False)
    needs_new_selfie = models.BooleanField(default=False)
    # An advisory hint for the admin, never a decision: how alike the two faces look (see face_match.py), and the
    # model that said so, or why there is no score.
    face_match_score = models.FloatField(null=True, blank=True)
    face_match_model = models.CharField(max_length=120, blank=True)
    # When an admin last approved or rejected the check. The ID and selfie images are deleted 90 days later.
    verification_decided_at = models.DateTimeField(null=True, blank=True)
    # A keyed hash of the ID number and its last 3 characters. Kept after the number and images are deleted, so a
    # second account with the same ID can still be spotted. See id_privacy.py.
    id_number_hash = models.CharField(max_length=64, blank=True, db_index=True)
    id_number_last3 = models.CharField(max_length=3, blank=True)
    # When purge_id_images (or deleting the account) removed the images and the plain number.
    id_images_purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'], name='profile_search_vector_gin'),
        ]

    def __str__(self):
        return f'FreelancerProfile<{self.user.email}>'

    @property
    def verified(self):
        return self.verification_status == self.VerificationStatus.VERIFIED


class PortfolioItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    freelancer = models.ForeignKey(
        FreelancerProfile, on_delete=models.CASCADE, related_name='portfolio_items'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    link = models.URLField(blank=True)
    image = models.ImageField(upload_to='portfolio/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class VerificationChallenge(models.Model):
    """A random gesture to perform in the selfie. Single use, and only good for ten minutes (see selfie.py)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='verification_challenges')
    text = models.CharField(max_length=200)
    issued_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return f'Challenge<{self.user_id}: {self.text}>'
