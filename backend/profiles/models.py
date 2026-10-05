import uuid

from django.conf import settings
from django.db import models

from .counties import COUNTY_CHOICES
from .skills import display_name, match_key


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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='freelancer_profile'
    )
    skills = models.ManyToManyField(Skill, related_name='freelancers', blank=True)
    bio = models.CharField(max_length=300, blank=True)
    county = models.CharField(max_length=40, choices=COUNTY_CHOICES, null=True, blank=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    # write-only in every serializer — never include in a response, even to the owner
    id_number = models.CharField(max_length=20, blank=True)
    id_document = models.FileField(upload_to='id_documents/', blank=True, null=True)
    verification_status = models.CharField(
        max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.UNVERIFIED
    )

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
