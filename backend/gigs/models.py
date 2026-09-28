import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.utils.text import slugify

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


class Gig(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CLOSED = 'closed', 'Closed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='gigs')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='gigs')
    title = models.CharField(max_length=200)
    description = models.TextField()
    budget_min = models.DecimalField(max_digits=10, decimal_places=2)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    deadline = models.DateField()
    # Last day to apply — distinct from `deadline` (project delivery date). Nullable at the
    # column level so it *can* be omitted on input, but save() always fills it in, so it's
    # functionally never null once persisted.
    application_deadline = models.DateField(null=True, blank=True)
    is_negotiable = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    skills = models.ManyToManyField(Skill, through='GigSkill', related_name='gigs')
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Trigram GIN index — supports Sprint 3's full-text/partial search over description.
            GinIndex(fields=['description'], name='gig_description_gin', opclasses=['gin_trgm_ops']),
        ]

    def save(self, *args, **kwargs):
        if self.application_deadline is None:
            self.application_deadline = self.deadline
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


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
