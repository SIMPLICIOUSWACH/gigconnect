import uuid
from datetime import timedelta

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import serializers

from profiles.models import Skill

from .models import Category

SORT_CHOICES = ['newest', 'deadline', 'budget_high', 'budget_low', 'relevance']


class GigFilterSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    category = serializers.CharField(required=False, allow_blank=True)
    skills = serializers.CharField(required=False, allow_blank=True)
    budget_min = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    budget_max = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    # DRF's BooleanField implicitly defaults to False (not "absent") when required=False,
    # since it's designed for HTML checkboxes that don't submit a value when unchecked.
    # allow_null + an explicit default=None overrides that so "not provided" really means
    # "don't filter on this" rather than "filter for non-negotiable gigs only".
    negotiable = serializers.BooleanField(required=False, allow_null=True, default=None)
    deadline_before = serializers.DateField(required=False)
    posted_within = serializers.IntegerField(required=False)
    sort = serializers.ChoiceField(choices=SORT_CHOICES, required=False, default='newest')

    def validate_posted_within(self, value):
        if value not in (1, 7, 30):
            raise serializers.ValidationError('Must be one of 1, 7, or 30.')
        return value

    def validate_category(self, value):
        value = value.strip()
        if value and not Category.objects.filter(slug=value).exists():
            raise serializers.ValidationError(f'Unknown category slug "{value}".')
        return value

    def validate(self, attrs):
        budget_min = attrs.get('budget_min')
        budget_max = attrs.get('budget_max')
        if budget_min is not None and budget_max is not None and budget_min > budget_max:
            raise serializers.ValidationError(
                {'budget_min': 'budget_min must not be greater than budget_max.'}
            )

        # Graceful fallback, not an error — the spec explicitly calls this out as such.
        if attrs.get('sort') == 'relevance' and not attrs.get('q'):
            attrs['sort'] = 'newest'

        return attrs


def _resolve_skill_ids(raw):
    """Comma-separated skill UUIDs or names -> list of matching Skill ids.

    Unknown tokens are silently dropped (they just contribute no matches) rather than
    rejected — unlike an unknown category slug, an unrecognised skill name isn't malformed
    input, it just doesn't exist yet.
    """
    tokens = [t.strip() for t in raw.split(',') if t.strip()]
    if not tokens:
        return []

    query = Q()
    matched_any = False
    for token in tokens:
        try:
            uuid.UUID(token)
            query |= Q(id=token)
            matched_any = True
        except ValueError:
            query |= Q(name__iexact=token)
            matched_any = True

    if not matched_any:
        return []
    return list(Skill.objects.filter(query).values_list('id', flat=True))


def apply_gig_filters(queryset, data):
    """Apply validated GigFilterSerializer data to a Gig queryset. All filters AND together."""
    q = data.get('q')
    if q:
        search_query = SearchQuery(q, search_type='websearch')
        queryset = queryset.filter(search_vector=search_query).annotate(
            rank=SearchRank(F('search_vector'), search_query)
        )

    category_slug = data.get('category')
    if category_slug:
        queryset = queryset.filter(category__slug=category_slug)

    skills_raw = data.get('skills')
    if skills_raw:
        skill_ids = _resolve_skill_ids(skills_raw)
        queryset = queryset.filter(skills__id__in=skill_ids).distinct()

    budget_min = data.get('budget_min')
    if budget_min is not None:
        queryset = queryset.filter(budget_max__gte=budget_min)

    budget_max = data.get('budget_max')
    if budget_max is not None:
        queryset = queryset.filter(budget_min__lte=budget_max)

    negotiable = data.get('negotiable')
    if negotiable is not None:
        queryset = queryset.filter(is_negotiable=negotiable)

    deadline_before = data.get('deadline_before')
    if deadline_before is not None:
        queryset = queryset.filter(deadline__lte=deadline_before)

    posted_within = data.get('posted_within')
    if posted_within is not None:
        since = timezone.now() - timedelta(days=posted_within)
        queryset = queryset.filter(created_at__gte=since)

    sort = data.get('sort', 'newest')
    if sort == 'relevance':
        queryset = queryset.order_by('-rank', '-created_at')
    elif sort == 'deadline':
        queryset = queryset.order_by('deadline')
    elif sort == 'budget_high':
        queryset = queryset.order_by('-budget_max')
    elif sort == 'budget_low':
        queryset = queryset.order_by('budget_min')
    else:
        queryset = queryset.order_by('-created_at')

    return queryset
