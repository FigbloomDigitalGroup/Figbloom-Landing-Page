import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent          # → backend/
FRONTEND_DIR = BASE_DIR.parent / 'frontend'                  # → frontend/

# Load backend/.env for local development. On Render, real environment
# variables are set in the dashboard / render.yaml, so this is a no-op.
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name):
    return [item.strip() for item in os.environ.get(name, '').split(',') if item.strip()]


# --- Core ---------------------------------------------------------------

# Generated per-service by Render (see render.yaml). The fallback exists so
# `manage.py` still runs locally without a .env file — never used in production.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-local-development-only-do-not-use-in-production',
)

# Defaults to False so a missing env var can never expose tracebacks in
# production. Set DJANGO_DEBUG=true in backend/.env for local development.
DEBUG = env_bool('DJANGO_DEBUG', default=False)

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# Render injects the service's public hostname at runtime.
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Any custom domain(s) pointed at the service, comma separated.
ALLOWED_HOSTS += env_list('DJANGO_ALLOWED_HOSTS')

# Django requires an explicit scheme here for cross-origin POSTs over HTTPS.
CSRF_TRUSTED_ORIGINS = [
    f'https://{host}' for host in ALLOWED_HOSTS
    if host not in ('127.0.0.1', 'localhost')
]
CSRF_TRUSTED_ORIGINS += ['http://127.0.0.1:8000', 'http://localhost:8000']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'corsheaders',
    'storages',
    'careers',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise serves frontend/ and staticfiles/ directly from gunicorn;
    # it must sit immediately after SecurityMiddleware.
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
        'DIRS': [FRONTEND_DIR],
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

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- Database -----------------------------------------------------------

# Render sets DATABASE_URL from the Postgres instance in render.yaml.
# Locally, with no DATABASE_URL, this falls back to the existing SQLite file.
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

LOGIN_URL = '/admin-dashboard/login'


# --- Static files -------------------------------------------------------

# STATIC_URL only covers Django's own assets (admin, DRF browsable API).
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# The landing page's HTML references /assets/... and /components/... at the
# site root, so WhiteNoise serves frontend/ verbatim from the root URL. This
# also covers robots.txt, sitemap.xml and the Google verification file.
WHITENOISE_ROOT = FRONTEND_DIR
# Leave off so `/` and `/career` keep routing to config.views, not to the
# raw index.html files sitting in frontend/.
WHITENOISE_INDEX_FILE = False
WHITENOISE_AUTOREFRESH = DEBUG


# --- Media / applicant CV uploads --------------------------------------

# Render's filesystem is ephemeral, so uploads must go to object storage in
# production. Setting AWS_STORAGE_BUCKET_NAME switches JobApplication.cv_file
# over to S3; without it (local dev) uploads land in backend/media/.
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', '')
USE_S3 = bool(AWS_STORAGE_BUCKET_NAME)

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        # Compresses but does not hash filenames — avoids collectstatic
        # failing on third-party CSS that references missing assets.
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

if USE_S3:
    STORAGES['default'] = {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'bucket_name': AWS_STORAGE_BUCKET_NAME,
            'access_key': os.environ.get('AWS_ACCESS_KEY_ID'),
            'secret_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
            # 'auto' for Cloudflare R2; a real region for AWS S3.
            'region_name': os.environ.get('AWS_S3_REGION_NAME', 'auto'),
            # Leave unset for AWS S3; set it for R2 / B2 / Spaces.
            'endpoint_url': os.environ.get('AWS_S3_ENDPOINT_URL') or None,
            'signature_version': 's3v4',
            'location': 'media',
            # CVs are personal data: keep the bucket private and hand out
            # short-lived signed URLs instead of public links.
            'default_acl': None,
            'querystring_auth': True,
            'querystring_expire': 3600,
            'file_overwrite': False,
        },
    }


# --- Email --------------------------------------------------------------

EMAIL_BACKEND = os.environ.get(
    'DJANGO_EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
DEFAULT_FROM_EMAIL = os.environ.get('DJANGO_DEFAULT_FROM_EMAIL', 'noreply@figbloom.com')


# --- CORS ---------------------------------------------------------------

# In production the frontend is same-origin, so these only matter when the
# static pages are opened from a Live Server during local development.
CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:5500",
    "http://127.0.0.1:5501",
    "http://localhost:5500",
    "http://localhost:5501",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
] + env_list('DJANGO_CORS_ALLOWED_ORIGINS')

CORS_ALLOW_CREDENTIALS = True


# --- Production security ------------------------------------------------

if not DEBUG:
    # Render terminates TLS at its proxy and forwards this header.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', default=True)

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
    X_FRAME_OPTIONS = 'DENY'
