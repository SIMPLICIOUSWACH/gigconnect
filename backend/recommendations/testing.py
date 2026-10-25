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
