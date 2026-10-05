import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramWordSimilarity
from django.db.models import Case, Count, F, FloatField, Q, When
from django.db.models.functions import Greatest
from django.utils import timezone
from rest_framework import serializers

from profiles.counties import KENYA_COUNTIES
from profiles.models import Skill
from profiles.skills import find_skill

from .models import Category, Gig

SORT_CHOICES = ['newest', 'deadline', 'budget_high', 'budget_low', 'relevance']


class GigFilterSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    category = serializers.CharField(required=False, allow_blank=True)
    skills = serializers.CharField(required=False, allow_blank=True)
    skills_mode = serializers.ChoiceField(choices=['any', 'all'], required=False, default='any')
    budget_min = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    budget_max = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    # DRF's BooleanField implicitly defaults to False (not "absent") when required=False,
    # since it's designed for HTML checkboxes that don't submit a value when unchecked.
    # allow_null + an explicit default=None overrides that so "not provided" really means
    # "don't filter on this" rather than "filter for non-negotiable gigs only".
    negotiable = serializers.BooleanField(required=False, allow_null=True, default=None)
    include_closed = serializers.BooleanField(required=False, allow_null=True, default=None)
    county = serializers.ChoiceField(choices=KENYA_COUNTIES, required=False)
    remote = serializers.BooleanField(required=False, allow_null=True, default=None)
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

        # Graceful fallback, not an error: relevance needs a text query or skills to rank by.
        if attrs.get('sort') == 'relevance' and not attrs.get('q') and not attrs.get('skills'):
            attrs['sort'] = 'newest'

        return attrs


def _resolve_skills(raw):
    """Comma-separated skill UUIDs or names -> (set of matching Skill ids, count of unmatched tokens).

    Unknown tokens never raise: an unrecognised skill name isn't malformed input, it just
    doesn't exist (unlike an unknown category slug). They only matter for skills_mode=all,
    where a skill nobody has can't be satisfied.
    """
    ids = set()
    unresolved = 0
    for token in (t.strip() for t in raw.split(',')):
        if not token:
            continue
        try:
            uuid.UUID(token)
            skill_id = Skill.objects.filter(id=token).values_list('id', flat=True).first()
        except ValueError:
            skill = find_skill(token)  # case/spacing-insensitive, and resolves aliases (JS -> JavaScript)
            skill_id = skill.id if skill else None
        if skill_id is None:
            unresolved += 1
        else:
            ids.add(skill_id)
    return ids, unresolved


def _apply_text_search(queryset, q):
    """Full-text search on `q`, topped up with trigram matches when it finds too few gigs.

    Runs after every other filter, so "too few" means too few in the final result set. Exact
    full-text matches always rank above fuzzy-only ones (their rank is offset by 2, and a
    similarity score is at most 1).
    """
    search_query = SearchQuery(q, search_type='websearch')
    exact = queryset.filter(search_vector=search_query)
    if exact.count() >= settings.SEARCH_FALLBACK_MIN_RESULTS:
        return exact.annotate(rank=SearchRank(F('search_vector'), search_query))

    similarity = Greatest(TrigramWordSimilarity(q, 'title'), TrigramWordSimilarity(q, 'description'))
    return (
        queryset.annotate(similarity=similarity)
        .filter(Q(search_vector=search_query) | Q(similarity__gte=settings.SEARCH_TRIGRAM_THRESHOLD))
        .annotate(
            rank=Case(
                When(search_vector=search_query, then=SearchRank(F('search_vector'), search_query) + 2.0),
                default=F('similarity'),
                output_field=FloatField(),
            )
        )
    )


def apply_gig_filters(queryset, data):
    """Apply validated GigFilterSerializer data to a Gig queryset. All filters AND together."""
    category_slug = data.get('category')
    if category_slug:
        queryset = queryset.filter(category__slug=category_slug)

    skills_raw = data.get('skills')
    if skills_raw:
        skill_ids, unresolved = _resolve_skills(skills_raw)
        if data.get('skills_mode') == 'all' and (unresolved or not skill_ids):
            queryset = queryset.none()  # a skill that doesn't exist can't be matched by any gig
        else:
            queryset = queryset.filter(skills__id__in=skill_ids).annotate(
                matched_skills=Count('skills', distinct=True)
            )
            if data.get('skills_mode') == 'all':
                queryset = queryset.filter(matched_skills=len(skill_ids))

    budget_min = data.get('budget_min')
    budget_max = data.get('budget_max')
    if budget_min is not None or budget_max is not None:
        # budget_min/budget_max are always given in KES, so a budget comparison can only be
        # meaningful against KES rows — excluding anything else here (there shouldn't be any
        # going forward; see GigValidationMixin) rather than comparing numbers across currencies.
        queryset = queryset.filter(currency=Gig.CURRENCY_KES)
    if budget_min is not None:
        queryset = queryset.filter(budget_max__gte=budget_min)
    if budget_max is not None:
        queryset = queryset.filter(budget_min__lte=budget_max)

    negotiable = data.get('negotiable')
    if negotiable is not None:
        queryset = queryset.filter(is_negotiable=negotiable)

    county = data.get('county')
    if county:
        queryset = queryset.filter(county=county)

    remote = data.get('remote')
    if remote is not None:
        queryset = queryset.filter(is_remote=remote)

    deadline_before = data.get('deadline_before')
    if deadline_before is not None:
        queryset = queryset.filter(deadline__lte=deadline_before)

    posted_within = data.get('posted_within')
    if posted_within is not None:
        since = timezone.now() - timedelta(days=posted_within)
        queryset = queryset.filter(created_at__gte=since)

    q = data.get('q')
    if q:
        queryset = _apply_text_search(queryset, q)

    sort = data.get('sort', 'newest')
    if sort == 'relevance':
        # Skills matched first, then text rank, then newest. Either part is skipped when the
        # request has no skills / no q.
        order = []
        if data.get('skills'):
            order.append('-matched_skills')
        if q:
            order.append('-rank')
        queryset = queryset.order_by(*order, '-created_at')
    elif sort == 'deadline':
        queryset = queryset.order_by('deadline')
    elif sort == 'budget_high':
        queryset = queryset.order_by('-budget_max')
    elif sort == 'budget_low':
        queryset = queryset.order_by('budget_min')
    else:
        queryset = queryset.order_by('-created_at')

    return queryset
