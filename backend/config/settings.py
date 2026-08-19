import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()    

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

# Every *.onrender.com host, so the service works even when
# RENDER_EXTERNAL_HOSTNAME is not present in the runtime environment.
# Without this, a deploy where that variable is missing answers HTTP 400
# (DisallowedHost) to *every* request — including Render's health check on "/",
# so the deploy never goes live and is shut down. Relying on the variable alone
# is a single point of failure for the whole service.
ALLOWED_HOSTS.append('.onrender.com')

# The production domain, defaulted here rather than left to the dashboard so a
# missing env var can never take the site down again. DJANGO_ALLOWED_HOSTS below
# still works for anything additional.
ALLOWED_HOSTS += ['figbloom.org', 'www.figbloom.org']

# Any further custom domain(s) pointed at the service, comma separated.
ALLOWED_HOSTS += env_list('DJANGO_ALLOWED_HOSTS')

# Django requires an explicit scheme here for cross-origin POSTs over HTTPS.
# A leading-dot wildcard host ('.onrender.com') has to be written as
# 'https://*.onrender.com' for CSRF — the bare dotted form is not accepted.
CSRF_TRUSTED_ORIGINS = [
    'https://{}'.format('*' + host if host.startswith('.') else host)
    for host in ALLOWED_HOSTS
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
# production. Setting CLOUDINARY_URL switches JobApplication.cv_file over to
# Cloudinary; without it (local dev) uploads land in backend/media/.
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

USE_CLOUDINARY = bool(os.environ.get('CLOUDINARY_URL'))

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

if USE_CLOUDINARY:
    INSTALLED_APPS += ['cloudinary_storage', 'cloudinary']
    STORAGES['default'] = {
        'BACKEND': 'cloudinary_storage.storage.RawMediaCloudinaryStorage',
    }
    # CLOUDINARY_URL (cloudinary://<key>:<secret>@<cloud_name>) is read
    # automatically by the cloudinary SDK — no extra config needed here.


# --- Email --------------------------------------------------------------
# Superseded by MAILERS below (Django 6.1 forbids defining both).


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
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
X_FRAME_OPTIONS = "SAMEORIGIN"

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = os.getenv("EMAIL_HOST", "lon105.truehost.cloud")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))

# Truehost (figbloom.org's mail host, per its MX record) uses implicit SSL
# on 465, not STARTTLS on 587 — Django rejects a settings.py where both are
# true, so these stay mutually exclusive. The hostname here is the mail
# server's real name (lon105.truehost.cloud), confirmed reachable — the
# generic "mail.figbloom.org" from Truehost's client-config instructions
# has no DNS record at all. Both flags are env-var-driven, not hardcoded,
# so switching provider or port again later needs only a dashboard edit.
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "true").lower() == "true"
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "false").lower() == "true"

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

# Most SMTP servers reject or flag a From address that doesn't match (or
# share a domain with) the authenticated account, so this should track
# whichever mailbox EMAIL_HOST_USER actually is.
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "Figbloom Digital Group <support@figbloom.org>"
)


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
