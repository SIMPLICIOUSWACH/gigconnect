"""
Find freelancers: who can be found, how the search and filters work, and what a result card contains.

Only clients and admins search. A freelancer appears when their account is active, email-verified, not suspended or
deleted, and they have left "Show my profile in Find freelancers" on. Synthetic seed accounts follow the same
SHOW_SYNTHETIC rule as gigs. A card never carries an email, phone number, ID number or document: it is built field by
field in card() below, not from a model serializer.

Keyword search works like the gig search: full-text over a weighted vector (name and headline, then skills, then bio),
topped up with trigram matches when that finds too few, so a typo still finds someone.
"""

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, TrigramWordSimilarity
from django.db.models import Case, Count, F, FloatField, Q, Value, When
from django.db.models.functions import Greatest
from rest_framework import serializers

from accounts.models import User
from applications.models import Application
from gigs.filters import _resolve_skills
from gigs.models import Gig
from reviews.service import bayesian_rating

from .counties import KENYA_COUNTIES
from .models import FreelancerProfile

SORT_CHOICES = ['best_match', 'rating', 'completed', 'newest']
PAGE_SIZE = 12
# Without a keyword or a filter, the list stops here: nobody needs to page through every freelancer.
MAX_UNFILTERED_PAGES = 50
TOP_SKILLS = 5


def update_search_vector(profile):
    """Recompute one profile's search vector. A queryset update, so it never triggers post_save again."""
    skill_names = ' '.join(profile.skills.values_list('name', flat=True))
    vector = (
        SearchVector(Value(profile.user.full_name), weight='A')
        + SearchVector('headline', weight='A')
        + SearchVector(Value(skill_names), weight='B')
        + SearchVector('bio', weight='C')
    )
    FreelancerProfile.objects.filter(pk=profile.pk).update(search_vector=vector)


def findable_freelancers():
    """The profiles that may appear in Find freelancers and in "Suggested for this gig"."""
    profiles = FreelancerProfile.objects.filter(
        search_visible=True,
        user__role=User.Role.FREELANCER, user__is_active=True, user__is_email_verified=True,
        user__account_status=User.AccountStatus.ACTIVE, user__deleted_at__isnull=True,
    )
    if not settings.SHOW_SYNTHETIC:
        profiles = profiles.filter(user__is_synthetic=False)
    return profiles


class FreelancerFilterSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True, max_length=100)
    skills = serializers.CharField(required=False, allow_blank=True)
    county = serializers.ChoiceField(choices=KENYA_COUNTIES, required=False)
    # allow_null with default None: "not given" must mean "don't filter", not False (see GigFilterSerializer).
    remote = serializers.BooleanField(required=False, allow_null=True, default=None)
    verified = serializers.BooleanField(required=False, allow_null=True, default=None)
    available = serializers.BooleanField(required=False, allow_null=True, default=None)
    min_rating = serializers.DecimalField(max_digits=2, decimal_places=1, min_value=1, max_value=5, required=False)
    sort = serializers.ChoiceField(choices=SORT_CHOICES, required=False, default='best_match')

    def narrowed(self):
        """True when there is a keyword or any filter: an unfiltered list can't be paged through for ever."""
        data = self.validated_data
        return bool(
            data.get('q') or data.get('skills') or data.get('county') or data.get('min_rating') is not None
            or data.get('remote') or data.get('verified') or data.get('available')
        )


def _apply_text_search(profiles, q):
    """Full-text matches, topped up with trigram matches when there are too few. Exact matches always rank first."""
    query = SearchQuery(q, search_type='websearch')
    exact = profiles.filter(search_vector=query)
    if exact.count() >= settings.SEARCH_FALLBACK_MIN_RESULTS:
        return exact.annotate(rank=SearchRank(F('search_vector'), query))
    similarity = Greatest(
        TrigramWordSimilarity(q, 'user__full_name'), TrigramWordSimilarity(q, 'headline'),
        TrigramWordSimilarity(q, 'bio'),
    )
    return (
        profiles.annotate(similarity=similarity)
        .filter(Q(search_vector=query) | Q(similarity__gte=settings.SEARCH_TRIGRAM_THRESHOLD))
        .annotate(rank=Case(
            When(search_vector=query, then=SearchRank(F('search_vector'), query) + 2.0),
            default=F('similarity'), output_field=FloatField(),
        ))
    )


def search(data):
    """Apply validated FreelancerFilterSerializer data. Returns an ordered FreelancerProfile queryset."""
    profiles = findable_freelancers()

    if data.get('county'):
        profiles = profiles.filter(county=data['county'])
    if data.get('remote'):
        profiles = profiles.filter(open_to_remote=True)
    if data.get('verified'):
        profiles = profiles.filter(verification_status=FreelancerProfile.VerificationStatus.VERIFIED)
    if data.get('available'):
        profiles = profiles.filter(is_available=True)
    if data.get('min_rating') is not None:
        # Someone with no reviews has no rating to compare, so a minimum leaves them out.
        profiles = profiles.filter(rating_count__gt=0, rating_avg__gte=data['min_rating'])

    by_skills = False
    if data.get('skills'):
        skill_ids, _ = _resolve_skills(data['skills'])
        profiles = profiles.filter(skills__id__in=skill_ids).annotate(
            matched_skills=Count('skills', filter=Q(skills__id__in=skill_ids), distinct=True),
        )
        by_skills = True

    q = data.get('q')
    if q:
        profiles = _apply_text_search(profiles, q)

    completed = Q(
        user__applications__status=Application.Status.HIRED, user__applications__gig__status=Gig.Status.COMPLETED,
    )
    profiles = profiles.annotate(
        gigs_completed=Count('user__applications', filter=completed, distinct=True),
        bayesian=bayesian_rating(),
    )

    verified_first = Case(
        When(verification_status=FreelancerProfile.VerificationStatus.VERIFIED, then=Value(0)), default=Value(1),
    )
    recently_active = F('user__last_login').desc(nulls_last=True)
    sort = data.get('sort') or 'best_match'
    if sort == 'rating':
        order = ['-bayesian', '-rating_count', recently_active]
    elif sort == 'completed':
        order = ['-gigs_completed', '-bayesian', recently_active]
    elif sort == 'newest':
        order = ['-user__created_at']
    elif q:
        order = ['-rank', '-bayesian', recently_active]
    elif by_skills:
        order = ['-matched_skills', '-bayesian', recently_active]
    else:
        # Nothing to match against: verified people first, then the Bayesian rating, then who was here last.
        order = [verified_first, '-bayesian', recently_active]
    return profiles.select_related('user').prefetch_related('skills').order_by(*order, 'pk')


def card(profile, request=None, gigs_completed=None):
    """What a client sees of a freelancer in a list. Public fields only, chosen one by one."""
    photo = profile.profile_photo.url if profile.profile_photo else None
    if photo and request is not None:
        photo = request.build_absolute_uri(photo)
    skills = list(profile.skills.all())
    if gigs_completed is None:
        gigs_completed = getattr(profile, 'gigs_completed', 0)
    return {
        'id': str(profile.user_id),
        'full_name': profile.user.full_name,
        'profile_photo': photo,
        'profile_colour': profile.profile_colour,
        'verified': profile.verified,
        'headline': profile.headline,
        'county': profile.county,
        'skills': [{'id': str(skill.pk), 'name': skill.name} for skill in skills[:TOP_SKILLS]],
        'skills_total': len(skills),
        'rating_avg': profile.rating_avg,
        'rating_count': profile.rating_count,
        'gigs_completed': gigs_completed,
        'starting_price': profile.starting_price,
        'is_available': profile.is_available,
        'open_to_remote': profile.open_to_remote,
    }
