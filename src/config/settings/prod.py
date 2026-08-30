"""Production settings — Clawsrv deploy (D-28). Normally runs behind the
host's existing Caddy, which terminates TLS and reverse-proxies to `web`
on 127.0.0.1:8102 (docker-compose.yml, §17.5); Django still enforces the
security headers below in case it is ever reached directly.

`DJANGO_TLS` (default true): the interim raw-IP:port deploy (no Caddy
site block yet, pending real hostnames — docs/GO_LIVE_PREP_SHEET.md) has
no TLS anywhere in front of it. The TLS-dependent settings below
(SSL redirect, Secure cookies, HSTS) would either infinite-redirect or —
worse — silently drop the session/CSRF cookies a browser refuses to send
`Secure` cookies over plain HTTP, breaking staff login outright) if left
on without HTTPS actually terminating somewhere. Set `DJANGO_TLS=false`
in .env for that phase only; flip it back to true (or just unset it) the
same day a real domain + Caddy + TLS exist — no code change needed.
"""
from .base import *  # noqa: F401,F403

DEBUG = False

# WhiteNoise serves STATIC_ROOT directly from the gunicorn process — no
# host Caddy in front yet for the raw IP:port deploy (D-28's real reverse
# proxy is pending real hostnames). Inserted right after
# SecurityMiddleware, WhiteNoise's own requirement. Prod-only: dev/test
# serve static files a different way (see settings/base.py's MIDDLEWARE
# comment) and never run collectstatic, so STATIC_ROOT doesn't exist
# there — WhiteNoise warns on every request if it's missing.
MIDDLEWARE = MIDDLEWARE[:1] + ["whitenoise.middleware.WhiteNoiseMiddleware"] + MIDDLEWARE[1:]

# Hashed filenames + far-future caching, paired with WhiteNoiseMiddleware
# above. Requires `manage.py collectstatic` to have already run (baked
# into the Docker image build, see repo-root Dockerfile) — that's exactly
# why this isn't in base.py: dev/test never run collectstatic, and this
# backend raises on every `{% static %}` lookup without its manifest file.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

if not ALLOWED_HOSTS or ALLOWED_HOSTS == ["*"]:
    # Appendix D's SITE_URL gives us at least the canonical host even if
    # ALLOWED_HOSTS itself was left unset.
    from urllib.parse import urlparse

    _site_host = urlparse(SITE_URL).hostname
    ALLOWED_HOSTS = [_site_host] if _site_host else []

TLS = env.bool("DJANGO_TLS", default=True)

if TLS:
    # Caddy (§17.5) terminates TLS and forwards over plain HTTP on the
    # loopback interface, so Django must trust X-Forwarded-Proto rather
    # than requiring the socket itself to be TLS.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
REFERRER_POLICY = "strict-origin-when-cross-origin"

if SENTRY_DSN:
    # sentry-sdk is a pinned dependency (pyproject.toml); wiring it up with
    # its Django integration is left for the milestone that adds real
    # error paths worth tracking — flagged here rather than silently
    # dropped.
    pass  # TODO: sentry_sdk.init(dsn=SENTRY_DSN, integrations=[DjangoIntegration()])
