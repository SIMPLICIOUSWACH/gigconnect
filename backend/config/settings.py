"""
Django settings for the GigConnect backend.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'gigconnect'),
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
# The most latent factors the SVD learns (fewer if the data is smaller). Below any of these three minimums
# the collaborative model is skipped altogether and the recommender uses content scores only.
RECOMMENDER_SVD_COMPONENTS = 20
RECOMMENDER_SVD_MIN_FREELANCERS = 10
RECOMMENDER_SVD_MIN_GIGS = 20
RECOMMENDER_SVD_MIN_INTERACTIONS = 100
RECOMMENDER_RANDOM_SEED = 42

# Whether recommendations are switched on at all. Off by default: with no trained model there is nothing
# honest to show, and the pages say so instead of guessing. Set RECOMMENDATIONS_ENABLED=True to turn on.
RECOMMENDATIONS_ENABLED = os.environ.get('RECOMMENDATIONS_ENABLED', 'False') == 'True'
# Where trained models are saved (not tracked by git).
RECOMMENDER_ARTIFACT_DIR = Path(
    os.environ.get('RECOMMENDER_ARTIFACT_DIR', BASE_DIR / 'recommendations' / 'artifacts')
)
# Whether training uses the synthetic seed rows by default. On in development, off otherwise, and the
# share of synthetic data is recorded on every trained model either way.
RECOMMENDER_INCLUDE_SYNTHETIC = os.environ.get('RECOMMENDER_INCLUDE_SYNTHETIC', str(DEBUG)) == 'True'
# Cold start: a freelancer who has interacted with fewer than this many different gigs gets content scores
# only. From there the weight on the collaborative score ramps up over the next RAMP gigs, to the maximum.
# These are starting values for Sprint 6 to tune on a validation split.
RECOMMENDER_COLD_START_MIN_GIGS = 5
RECOMMENDER_BLEND_RAMP_GIGS = 20
RECOMMENDER_BLEND_MAX_WEIGHT = 0.5
# How long a loaded model is trusted before the database is asked whether a newer one was trained.
RECOMMENDER_MODEL_CACHE_SECONDS = 60

# How a client's match score is described. These cut-offs come from the scores measured on the development
# data in Sprint 5, where freelancers sharing a skill with a gig had a median score of 0.15 and a 90th
# percentile of 0.31. That data is mostly synthetic, so they are provisional and Sprint 6 should recheck them.
# A band is only given when the freelancer and the gig really share a skill.
RECOMMENDER_BAND_STRONG = 0.30
RECOMMENDER_BAND_GOOD = 0.15
