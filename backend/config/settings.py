"""
Django settings for the GigConnect backend.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

from config import recommender_profiles

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-change-in-production')

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',

    'accounts',
    'profiles',
    'usersettings',
    'gigs',
    'applications',
    'recommendations',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# The recommender profile: which database and which tuned recommender settings the app runs with. The values are in
# config/recommender_profiles.json. RECOMMENDER_PROFILE=demo runs the planted database with the planted tuning pick;
# anything else is refused, and production is used when the variable is missing. See config/recommender_profiles.py.
RECOMMENDER_PROFILE, _PROFILE = recommender_profiles.resolve(os.environ)
RECOMMENDER_PROFILE_LABEL = _PROFILE['label']
RECOMMENDER_PLANTED_DATABASE = recommender_profiles.load()['demo']['database']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': recommender_profiles.database_name(_PROFILE, os.environ),
        'USER': os.environ.get('DB_USER', 'gigconnect'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'gigconnect'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Django's default password hasher is deliberately slow. The tests create hundreds of users, and with
# it the suite took about 20 minutes. They only need a hasher that works, so use a fast one when the
# command is `manage.py test`. Every other command, including runserver, keeps the strong default.
if sys.argv[1:2] == ['test']:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'skill_create': '30/hour',
        'gig_interaction': '300/hour',
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
}

CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS', 'http://localhost:5173'
).split(',')

# Console backend for dev — verification emails print to the runserver console.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'GigConnect <no-reply@gigconnect.local>'
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')

# Synthetic rows (from the seed and data-pipeline commands) are shown in the public feed in dev
# only, unless SHOW_SYNTHETIC is set explicitly.
SHOW_SYNTHETIC = os.environ.get('SHOW_SYNTHETIC', str(DEBUG)) == 'True'

# Typo-tolerant search: when full-text search returns fewer than this many gigs, results are
# merged with trigram word-similarity matches on title/description.
SEARCH_FALLBACK_MIN_RESULTS = int(os.environ.get('SEARCH_FALLBACK_MIN_RESULTS', '5'))
# 0.25 rather than pg_trgm's 0.3 default: a one-transposition typo like "pyhton" vs "python"
# only scores about 0.27-0.29, so 0.3 would miss the most common kind of typo.
SEARCH_TRIGRAM_THRESHOLD = float(os.environ.get('SEARCH_TRIGRAM_THRESHOLD', '0.25'))

# Recommendation engine (Sprint 5). Everything it is trained on lives in one visible folder at the
# root of the repo, so the data can be opened and checked. See datasets/README.md.
RECOMMENDER_DATA_DIR = Path(os.environ.get('RECOMMENDER_DATA_DIR', BASE_DIR.parent / 'datasets'))
# The most rows kept from each external job-posting source, so no single source drowns the others.
RECOMMENDER_CORPUS_MAX_ROWS = {'upwork': 15000, 'linkedin': 15000, 'freelancer': 3000}
# The share of documents the content model's vocabulary is fitted on that come from GigConnect's own gigs.
# The platform's gigs are repeated until they make up this share next to the external job postings, so a
# few hundred Kenyan gigs are not drowned out by tens of thousands of foreign ones.
RECOMMENDER_PLATFORM_SHARE = 0.3
# Words in fewer than this many documents, or in more than this share of them, are ignored by the vectoriser.
RECOMMENDER_TFIDF_MIN_DF = 3
RECOMMENDER_TFIDF_MAX_DF = 0.8

# The collaborative model learns from how much each freelancer has shown interest in each gig. Every kind of
# interaction has a weight, and a freelancer and gig pair is worth the strongest one (not the sum), so
# opening a gig fifty times counts the same as opening it once. A rejected or withdrawn application still
# counts as an application: the freelancer did apply.
RECOMMENDER_INTERACTION_WEIGHTS = {
    'view': 1, 'search_click': 1, 'recommendation_click': 1, 'save': 2, 'apply': 3,
}
RECOMMENDER_APPLICATION_WEIGHTS = {
    'pending': 3, 'under_review': 3, 'shortlisted': 4, 'hired': 5, 'rejected': 3, 'withdrawn': 3,
}
# The most latent factors the SVD learns (fewer if the data is smaller), from the profile. Below any of these three
# minimums the collaborative model is skipped altogether and the recommender uses content scores only.
RECOMMENDER_SVD_COMPONENTS = _PROFILE['svd_components']
RECOMMENDER_SVD_MIN_FREELANCERS = 10
RECOMMENDER_SVD_MIN_GIGS = 20
RECOMMENDER_SVD_MIN_INTERACTIONS = 100
RECOMMENDER_RANDOM_SEED = 42

# Whether recommendations are switched on at all. Off by default: with no trained model there is nothing
# honest to show, and the pages say so instead of guessing. Set RECOMMENDATIONS_ENABLED=True to turn on. The demo
# profile switches them on itself.
RECOMMENDATIONS_ENABLED = recommender_profiles.recommendations_enabled(_PROFILE, os.environ)
# Where trained models are saved (not tracked by git). The demo profile has a folder of its own inside it, so
# training the demo can never overwrite a production model.
RECOMMENDER_ARTIFACT_DIR = Path(
    os.environ.get('RECOMMENDER_ARTIFACT_DIR', BASE_DIR / 'recommendations' / 'artifacts' / _PROFILE['artifact_folder'])
)
# Where a training run writes its copy of the data it used, inside RECOMMENDER_DATA_DIR. The demo profile has its own.
RECOMMENDER_SNAPSHOT_FOLDER = _PROFILE['snapshot_folder']
# Whether training uses the synthetic seed rows by default. On in development, off otherwise, and the
# share of synthetic data is recorded on every trained model either way.
RECOMMENDER_INCLUDE_SYNTHETIC = os.environ.get('RECOMMENDER_INCLUDE_SYNTHETIC', str(DEBUG)) == 'True'
# Cold start: a freelancer who has interacted with fewer than this many different gigs gets content scores
# only. From there the weight on the collaborative score ramps up over the next RAMP gigs, to the maximum.
# The values come from the profile: tuned on the validation split in Sprint 6 (see docs/recommender.md).
RECOMMENDER_COLD_START_MIN_GIGS = _PROFILE['cold_start_min_gigs']
RECOMMENDER_BLEND_RAMP_GIGS = _PROFILE['blend_ramp_gigs']
RECOMMENDER_BLEND_MAX_WEIGHT = _PROFILE['blend_max_weight']
# How long a loaded model is trusted before the database is asked whether a newer one was trained.
RECOMMENDER_MODEL_CACHE_SECONDS = 60

# How a client's match score is described, from the profile. The cut-offs are the median ("good") and the 90th
# percentile ("strong") of the content scores of freelancer and gig pairs that share a skill, re-derived on the
# validation split in Sprint 6. The data is mostly synthetic, so they are provisional. A band is only given when
# the freelancer and the gig really share a skill.
RECOMMENDER_BAND_STRONG = _PROFILE['band_strong']
RECOMMENDER_BAND_GOOD = _PROFILE['band_good']
