"""Settings for the pytest run — `DJANGO_SETTINGS_MODULE=config.settings.test`
is set explicitly in pyproject.toml's `[tool.pytest.ini_options]`, which is
what pytest-django reads regardless of `DJANGO_ENV`.
"""
from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"  # noqa: S105 — test-only, never deployed

# Fast, insecure hasher: this project's own staff-password hashing is
# Argon2id via argon2-cffi (spec §4/D-12) applied explicitly in the auth
# code that will land with the staff-auth milestone; PASSWORD_HASHERS here
# only affects django.contrib.auth's own User model / test fixtures, and
# slow hashing would needlessly cost every test that touches a user.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

ALLOWED_HOSTS = ["*"]

# Unit tests (tests/unit) exercise pure functions in core/ (tz, phone,
# money) and never touch the database, so DATABASE_URL only matters for
# the integration/e2e layers (§20.5) — inherited from base.py's env lookup
# so CI/dev can point it at a real Postgres via the environment.
