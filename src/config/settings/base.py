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
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

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

# --- Object storage (self-hosted MinIO, D-28; Appendix D) ------------------
# django-storages wiring (AWS_S3_ENDPOINT_URL etc. / STORAGES backends) is
# milestone-2+ work once storage/ needs to actually read/write media; these
# are just the raw settings values so they exist and are validated early.
S3_ENDPOINT = env("S3_ENDPOINT", default="")
S3_PUBLIC_ENDPOINT = env("S3_PUBLIC_ENDPOINT", default="")
S3_REGION = env("S3_REGION", default="us-east-1")
S3_ACCESS_KEY = env("S3_ACCESS_KEY", default="")
S3_SECRET_KEY = env("S3_SECRET_KEY", default="")
S3_BUCKET_PROOFS = env("S3_BUCKET_PROOFS", default="curry-proofs")
S3_BUCKET_PUBLIC = env("S3_BUCKET_PUBLIC", default="curry-media")
CDN_BASE_URL = env("CDN_BASE_URL", default="")

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
