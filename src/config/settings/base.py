"""Shared Django settings. `dev.py` / `prod.py` / `test.py` import * from
here and override. Configuration is read from environment variables only
(spec §17.4), matching the list in `docs/SPEC_v1.1.md` Appendix D and
`.env.example`. Nothing here reads config from a file checked into the
repo other than an optional local `.env` for developer convenience.
"""
from __future__ import annotations

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

# src/config/settings/base.py -> src/config/settings -> src/config -> src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# repo root, one level above src/ — where `.env` and docker-compose.yml live
REPO_ROOT = BASE_DIR.parent

env = environ.Env()
_dotenv = REPO_ROOT / ".env"
if _dotenv.exists():
    # Local/dev convenience only. In containers (docker-compose.yml's
    # `env_file: .env`) the variables are already in the environment
    # before Python starts, so this is a no-op there.
    environ.Env.read_env(str(_dotenv))

# --- Django core (Appendix D) --------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-secret-key-change-me")
SITE_URL = env("SITE_URL", default="http://localhost:8102")

DEBUG = False
ALLOWED_HOSTS: list[str] = env.list("ALLOWED_HOSTS", default=["*"])

# --- Applications ----------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Needed for ArrayField / CITextField / partial-index Q() plumbing used
    # in core/models.py, and for the CITextExtension / CryptoExtension
    # migration operations that create the `citext` / `pgcrypto` extensions
    # schema_v1_1.sql expects.
    "django.contrib.postgres",
    # Project apps. Domain models live in `core` (§17.2: "core/ has no HTTP
    # imports"). NOTE (deviation from the brief): the staff-facing app is
    # named `staff`, not `manage` — see the long comment above STAFF_APP_NAME
    # below for why, and config/urls.py for how the /manage/ URL namespace
    # is preserved regardless.
    "core",
    "public",
    "staff",
    "jobs",
    "storage",
    "notifications",
]

# The brief asks for an app called `manage` (staff dashboard) living at
# src/manage/, alongside src/manage.py (the Django management script).
# Both would sit in the same `src/` directory added to sys.path by the
# editable install (`pyproject.toml`'s `[tool.setuptools.packages.find]
# where = ["src"]`). A directory package shadows a same-named .py module
# on the same sys.path entry, so `import manage` would resolve to the
# *app package*, never the script — and anything that ever did
# `python -m manage` or `importlib.import_module("manage")` would silently
# get the wrong thing. The brief itself flagged this exact risk and
# pre-approved the fallback: the Python package is named `staff` instead.
# The public URL prefix and template namespace stay `/manage/` and
# `manage:*` (see config/urls.py) so nothing the other agent's base.html
# assumes has to change.
STAFF_APP_NAME = "staff"  # documentation only, not read by Django

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoiseMiddleware is prod-only (settings/prod.py, inserted right
    # after SecurityMiddleware per WhiteNoise's own requirement) — dev
    # already serves static files directly from STATICFILES_DIRS via
    # Django's own runserver static handler (DEBUG=True), and neither
    # collects nor needs STATIC_ROOT to exist, which WhiteNoise warns
    # about on every request if it's missing.
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Sets request.staff_user (a core.User or None) from the session —
    # the staff-auth milestone's own middleware, independent of
    # AuthenticationMiddleware above (which is for django.contrib.admin's
    # unrelated auth). See staff/sessions.py's module docstring and
    # docs/DECISIONS.md D-33 for why staff auth doesn't use
    # django.contrib.auth at all. Must come after SessionMiddleware.
    "staff.middleware.StaffSessionMiddleware",
    "public.customer_middleware.CustomerSessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # CSP + Permissions-Policy (config/security_headers.py) — the two
    # security headers with no built-in Django setting. Everything else in
    # spec §20.5's "headers" line (X-Content-Type-Options, Referrer-Policy,
    # HSTS, X-Frame-Options) is Django's own SecurityMiddleware, configured
    # in settings/prod.py.
    "config.security_headers.SecurityHeadersMiddleware",
]

# D-12: "Session absolute lifetime 12 hours, sliding idle timeout 2
# hours". staff/sessions.py enforces both server-side on every request
# regardless of what the cookie itself says (never trust the client for
# this) — these two settings are the client-side backstop: the cookie's
# own Max-Age matches the absolute cap, and re-sending it on every
# request (rather than only when the session dict changes) lets it slide
# forward the same way the server-side idle timeout does.
SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_SAVE_EVERY_REQUEST = True
# SESSION_COOKIE_HTTPONLY/SAMESITE (both D-12-compliant by Django default)
# and SESSION_COOKIE_SECURE (True in prod.py; False here since local dev
# and CI run over plain HTTP) are set per-environment, not here.

ROOT_URLCONF = "config.urls"

# The other agent owns src/templates/base.html and src/static/ (design
# system CSS/JS/fonts) — these paths must point at exactly those
# directories and must not be created or written to by this task.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database ----------------------------------------------------------------
# psycopg[binary] (pinned in pyproject.toml) is picked up automatically by
# Django 5's "django.db.backends.postgresql" backend, which supports both
# psycopg2 and psycopg (3) — no separate backend name needed.
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://curry:curry@localhost:5432/curry",
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Timezone (spec §16: "DB stores UTC; tests pin the zone") --------------
# TIME_ZONE is fixed by product decision, not developer/deploy preference —
# still read from the environment (Appendix D lists it) but asserted so a
# misconfigured deploy fails at startup instead of quietly running business
# rules (cut-off, slots, trading days) against the wrong clock.
TIME_ZONE = env("TIME_ZONE", default="Africa/Johannesburg")
if TIME_ZONE != "Africa/Johannesburg":
    raise ImproperlyConfigured(
        f"TIME_ZONE must be 'Africa/Johannesburg' per spec Appendix D "
        f"(got {TIME_ZONE!r}). DB storage stays UTC (USE_TZ=True); this "
        f"only fixes the zone business rules are evaluated in."
    )
USE_TZ = True
USE_I18N = True
LANGUAGE_CODE = "en-za"

# --- Static files ------------------------------------------------------------
# Must match exactly where the other agent is writing (src/static/).
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = REPO_ROOT / "staticfiles"  # collectstatic target, not in src/
# WhiteNoise (MIDDLEWARE, below) serves STATIC_ROOT directly from the
# gunicorn process — no host Caddy in front yet for the raw IP:port
# deploy (D-28's real reverse proxy is pending real hostnames). The
# hashed-manifest storage backend that pairs with it
# (whitenoise.storage.CompressedManifestStaticFilesStorage) is prod-only
# (settings/prod.py) — it requires collectstatic to have already run to
# generate its manifest file, which dev/test never do; using it here
# would make every `{% static %}` tag raise in dev/test.

# --- Object storage (self-hosted MinIO, D-28; Appendix D) ------------------
# `storage.service` (milestone 4) uses these directly via boto3 when
# `S3_ENDPOINT` is set (Clawsrv/prod); when it's blank (local dev, tests —
# no MinIO container in either), it falls back to writing proofs under
# MEDIA_ROOT instead. Neither path goes through django-storages' FileField
# machinery — `core.Media.storage_key` is a plain text column, not a
# FileField, so a direct boto3/filesystem client is the natural fit; see
# storage/service.py's own module docstring.
S3_ENDPOINT = env("S3_ENDPOINT", default="")
S3_PUBLIC_ENDPOINT = env("S3_PUBLIC_ENDPOINT", default="")
S3_REGION = env("S3_REGION", default="us-east-1")
S3_ACCESS_KEY = env("S3_ACCESS_KEY", default="")
S3_SECRET_KEY = env("S3_SECRET_KEY", default="")
S3_BUCKET_PROOFS = env("S3_BUCKET_PROOFS", default="curry-proofs")
S3_BUCKET_PUBLIC = env("S3_BUCKET_PUBLIC", default="curry-media")
CDN_BASE_URL = env("CDN_BASE_URL", default="")

# Local-filesystem fallback used only when S3_ENDPOINT is unset (see
# above) — not part of the spec's own infrastructure (§17.2 names no
# local media path), purely a dev/test convenience so proof upload works
# without a running MinIO. Never referenced when S3_ENDPOINT is set.
MEDIA_ROOT = REPO_ROOT / "media"  # already gitignored
MEDIA_URL = "/media/"

# --- Backups (§15 / §17.1 — consumed by deploy/backup.sh, not Django itself) --
BACKUP_TARGET = env("BACKUP_TARGET", default="")
BACKUP_ENCRYPTION_KEY = env("BACKUP_ENCRYPTION_KEY", default="")

# --- Observability -----------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", default="")
GUNICORN_WORKERS = env.int("GUNICORN_WORKERS", default=3)
LOG_LEVEL = env("LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
}

# --- SMS (optional, D-07) ---------------------------------------------------
SMS_PROVIDER = env("SMS_PROVIDER", default="")
SMS_API_KEY = env("SMS_API_KEY", default="")
SMS_SENDER_ID = env("SMS_SENDER_ID", default="")

# --- Social auth (Google OAuth2, D-35) -------------------------------------
# Credentials from Google Cloud Console. Set to empty string in dev/test
# to disable social login (the login page still shows the button but
# the redirect returns an error from Google, not a server crash).
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")
# Bootstrap admin email — added to StaffAllowlist with role=admin on
# first deploy via: python manage.py bootstrap_admin
ADMIN_EMAIL = env("ADMIN_EMAIL", default="")

# --- Email backend (magic links, D-36) ------------------------------------
# Dev default: console (prints to stdout). Prod: SMTP via .env.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")
# Magic link token lifetime in minutes (D-36).
MAGIC_LINK_EXPIRY_MINUTES = env.int("MAGIC_LINK_EXPIRY_MINUTES", default=15)
