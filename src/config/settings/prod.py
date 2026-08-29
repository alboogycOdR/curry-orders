"""Production settings — Clawsrv deploy (D-28). Runs behind the host's
existing Caddy, which terminates TLS and reverse-proxies to `web` on
127.0.0.1:8102 (docker-compose.yml, §17.5); Django still enforces the
security headers below in case it is ever reached directly.
"""
from .base import *  # noqa: F401,F403

DEBUG = False

if not ALLOWED_HOSTS or ALLOWED_HOSTS == ["*"]:
    # Appendix D's SITE_URL gives us at least the canonical host even if
    # ALLOWED_HOSTS itself was left unset.
    from urllib.parse import urlparse

    _site_host = urlparse(SITE_URL).hostname
    ALLOWED_HOSTS = [_site_host] if _site_host else []

# Caddy (§17.5) terminates TLS and forwards over plain HTTP on the loopback
# interface, so Django must trust X-Forwarded-Proto rather than requiring
# the socket itself to be TLS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
REFERRER_POLICY = "strict-origin-when-cross-origin"

if SENTRY_DSN:
    # sentry-sdk is a pinned dependency (pyproject.toml); wiring it up with
    # its Django integration is left for the milestone that adds real
    # error paths worth tracking — flagged here rather than silently
    # dropped.
    pass  # TODO: sentry_sdk.init(dsn=SENTRY_DSN, integrations=[DjangoIntegration()])
