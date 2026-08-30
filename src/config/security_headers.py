"""Security response headers not already covered by Django's own
`SecurityMiddleware` (`X-Content-Type-Options`, `Referrer-Policy`,
`X-Frame-Options`, HSTS — all set via `settings/prod.py`, spec §16/§20.5's
own checklist line: "Token entropy, noindex, signed URL expiry, upload
validation, CSRF, headers, lockout").

Content-Security-Policy and Permissions-Policy have no built-in Django
setting, so this is a small hand-rolled middleware rather than pulling in
django-csp for two headers.

CSP trade-off, deliberately: `style-src`/`script-src` keep `'unsafe-inline'`.
This codebase's templates lean on inline `<style>` blocks throughout (the
Broadsheet design system) and a handful of inline `<script>`/`onclick`
(`public/checkout.html`, `public/reorder.html`, `staff/kitchen.html`) —
forbidding inline would break real pages, not just theoretical ones.
Moving those three templates' JS to `static/js/*.js` and switching to a
nonce- or hash-based CSP is a reasonable follow-up, not a blocker: even
with `'unsafe-inline'` on those two directives, this CSP still blocks the
attacker-relevant part of stored/reflected XSS (loading a payload or
exfiltrating data to an *external* origin), and closes the unrelated
plugin/frame/base-tag vectors outright.
"""
from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpRequest, HttpResponse


def _host(url: str) -> str | None:
    """`https://media.example.co.za/` -> `media.example.co.za`. Blank/unset
    settings (dev, test — no CDN/MinIO reachable from a browser) yield None,
    which callers skip, so img-src degrades to 'self' only."""
    if not url:
        return None
    return urlparse(url).netloc or None


def _build_csp() -> str:
    img_hosts = " ".join(
        h for h in (_host(settings.CDN_BASE_URL), _host(settings.S3_PUBLIC_ENDPOINT)) if h
    )
    img_src = f"'self' data: {img_hosts}".strip()
    directives = [
        "default-src 'self'",
        f"img-src {img_src}",
        "script-src 'self' 'unsafe-inline'",
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        # Belt-and-braces alongside X_FRAME_OPTIONS=DENY (settings/prod.py) —
        # frame-ancestors is the CSP-native, more-widely-honoured equivalent.
        "frame-ancestors 'none'",
    ]
    return "; ".join(directives)


# A food-ordering site with no camera/mic/geolocation/payment-API feature
# anywhere in the product — deny the lot rather than enumerate exceptions.
_PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
    "magnetometer=(), microphone=(), payment=(), usb=()"
)


class SecurityHeadersMiddleware:
    """Adds `Content-Security-Policy` and `Permissions-Policy` to every
    response. Computed once at import time (`_build_csp()` only reads
    settings, not the request) rather than per-request — these headers
    don't vary by request.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self._csp = _build_csp()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self._csp)
        response.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)
        return response
