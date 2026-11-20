"""
Step one of enrich_sample_data: make the sample profiles look lived in.

Freelancers get a headline, a starting price, a county, a mix of availability and remote settings, a generated avatar
and two to four portfolio items with generated covers. Clients get a company logo (and a company name if they had none).
A field that already holds something is never overwritten, and bios and skills are not touched at all, because the
recommender's content model reads them (see snapshot.py). Everything it changes is recorded in the ledger.
"""

from collections import Counter

from accounts.models import User
from profiles.counties import COUNTY_CHOICES
from profiles.models import ClientProfile, FreelancerProfile, PortfolioItem

from . import images, text

SAMPLE_EMAIL_SUFFIX = '@example.test'


def sample_users(role):
    """The synthetic accounts the seed commands made, in a fixed order. Never real accounts, never the showcase ones."""
    return User.objects.filter(
        role=role, is_synthetic=True, is_demo_extra=False, deleted_at__isnull=True, email__endswith=SAMPLE_EMAIL_SUFFIX,
    ).order_by('email')


def group_of(skill_names, rng=None):
    """The kind of work most of these skills belong to."""
    counts = Counter(text.SKILL_GROUP[name] for name in skill_names if name in text.SKILL_GROUP)
    if not counts:
        return 'business'
    top = max(counts.values())
    return sorted(group for group, number in counts.items() if number == top)[0]


def pick_county(rng):
    valid = {value for value, _ in COUNTY_CHOICES}
    pool = {county: weight for county, weight in text.COUNTY_WEIGHTS.items() if county in valid}
    return rng.choices(list(pool), weights=list(pool.values()))[0]


def round_to(amount, step):
    return int(round(amount / step) * step)


def fill_freelancer(ctx, user):
    ledger = ctx.ledger
    if ledger.is_done(user, 'profile'):
        return
    profile = user.freelancer_profile
    rng = ctx.rng('profile', user.email)
    group = group_of([skill.name for skill in profile.skills.all()])
    county = profile.county or pick_county(rng)

    changes = {}
    if not profile.county:
        changes['county'] = county
    if not profile.headline:
        changes['headline'] = rng.choice(text.HEADLINES[group]).format(county=county)
    if profile.starting_price is None:
        low, high = text.STARTING_PRICE_RANGE[group]
        changes['starting_price'] = round_to(rng.uniform(low, high), 500)
    # Toggles and colour have defaults, so there is no "blank" to wait for: set them once, and remember the old value.
    changes['is_available'] = rng.random() < 0.8
    changes['open_to_remote'] = rng.random() < 0.65
    colour = rng.choice(images.COLOUR_KEYS)
    changes['profile_colour'] = colour
    if not profile.profile_photo:
        changes['profile_photo'] = None  # filled below, once the colour is known

    for name, value in changes.items():
        ledger.remember(profile, name)
        if name != 'profile_photo':
            setattr(profile, name, value)
    if 'profile_photo' in changes:
        picture = images.avatar(user.full_name, colour)
        ctx.save_image(profile.profile_photo, f'sample-avatar-{user.pk.hex[:8]}.png', picture)
        ctx.count('avatars')
    profile.save(update_fields=list(changes))
    ctx.count('freelancer profiles filled')

    if profile.portfolio_items.count() < 2:
        titles = rng.sample(text.PORTFOLIO[group], k=rng.randint(2, 4))
        for position, (title, description) in enumerate(titles):
            item = PortfolioItem.objects.create(freelancer=profile, title=title, description=description)
            ledger.created(item)
            ctx.save_image(item.image, f'sample-cover-{item.pk.hex[:8]}.png', images.cover(title, colour, position))
            item.save(update_fields=['image'])
            ctx.count('portfolio items')
    ledger.mark_done(user, 'profile')


def fill_client(ctx, user):
    ledger = ctx.ledger
    if ledger.is_done(user, 'profile'):
        return
    profile = user.client_profile
    if not profile.company_name:
        ledger.remember(profile, 'company_name')
        profile.company_name = f'{user.full_name.split()[-1]} Enterprises'
        profile.save(update_fields=['company_name'])
    if not profile.company_logo:
        ledger.remember(profile, 'company_logo')
        colour = images.colour_for(profile.company_name)
        picture = images.logo(profile.company_name, colour)
        ctx.save_image(profile.company_logo, f'sample-logo-{user.pk.hex[:8]}.png', picture)
        profile.save(update_fields=['company_logo'])
        ctx.count('logos')
    ctx.count('client profiles filled')
    ledger.mark_done(user, 'profile')


def enrich_profiles(ctx):
    for user in sample_users(User.Role.FREELANCER):
        fill_freelancer(ctx, user)
    for user in sample_users(User.Role.CLIENT):
        fill_client(ctx, user)


__all__ = ['enrich_profiles', 'sample_users', 'group_of', 'FreelancerProfile', 'ClientProfile']
