"""
Settings that tests of the recommender's mechanics pin, so they test the mechanism and not whichever profile is
active. The production profile sets the collaborative weight to 0, which would turn every blend into content only,
and the band cut-offs change with each tuning.
"""

HYBRID_MECHANICS = {
    'RECOMMENDER_BLEND_MAX_WEIGHT': 0.5,
    'RECOMMENDER_BLEND_RAMP_GIGS': 20,
    'RECOMMENDER_COLD_START_MIN_GIGS': 5,
    'RECOMMENDER_SVD_COMPONENTS': 20,
}

BAND_CUT_OFFS = {'RECOMMENDER_BAND_GOOD': 0.15, 'RECOMMENDER_BAND_STRONG': 0.30}


PROFILE_SETTINGS = {
    'blend_max_weight': 'RECOMMENDER_BLEND_MAX_WEIGHT', 'blend_ramp_gigs': 'RECOMMENDER_BLEND_RAMP_GIGS',
    'cold_start_min_gigs': 'RECOMMENDER_COLD_START_MIN_GIGS', 'band_good': 'RECOMMENDER_BAND_GOOD',
    'band_strong': 'RECOMMENDER_BAND_STRONG',
}


def profile_settings(name):
    """The blend and band settings a profile gives, as Django settings, as if the server had restarted with it."""
    from config import recommender_profiles

    values = recommender_profiles.load()[name]
    return {setting: values[key] for key, setting in PROFILE_SETTINGS.items()}
