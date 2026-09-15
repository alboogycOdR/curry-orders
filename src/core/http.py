"""Small shared HTTP request helpers with no other natural home in
`core` (domain logic, no Django views of its own).
"""
from __future__ import annotations

from django.http import HttpRequest


def absolute_media_url(request: HttpRequest, url: str) -> str:
    """A JSON-API-safe absolute URL for a media path (e.g. dish photo).

    Plain `request.build_absolute_uri(url)` is *not* enough on its own:
    it trusts `request.is_secure()`, which is gated by
    `SECURE_PROXY_SSL_HEADER` — only set when `DJANGO_TLS=true`
    (`config/settings/prod.py`). `DJANGO_TLS` is deliberately kept
    `false` on the poster-variant deploy so the still-live raw-IP:port
    path (genuinely plain HTTP, no reverse proxy in front, correctly
    `http://`) doesn't get forced into `SECURE_SSL_REDIRECT`/`Secure`
    cookies. But that same deploy is *also* reachable through Caddy at
    `https://roticonnect.duckdns.org/` — Caddy terminates real TLS
    there and forwards to Django over plain HTTP internally, setting
    `X-Forwarded-Proto: https` on every such request regardless of
    whether Django is configured to trust it as its own
    "is this request secure" source. Without this function,
    `build_absolute_uri()` on that path produces an `http://` URL for a
    domain that never actually serves plain HTTP — invisible in a
    browser (an `<img src="http://...">` on an `https://` page still
    usually loads, browsers don't enforce mixed-content blocking as
    strictly for images as for scripts/xhr in every configuration) but
    fatal on Android: this project removed the app's cleartext-HTTP
    carve-out once this HTTPS domain existed
    (`mobile/android/app/src/main/res/xml/network_security_config.xml`,
    deleted 2026-09-15), so a real device flatly refuses to even
    attempt the request — found live the same day, after that same
    session's own earlier fix (routing this exact endpoint's photo_url
    through `build_absolute_uri()` at all, to fix a *different* bug —
    a bare relative path) had already shipped and been verified via a
    Flutter widget test. That test didn't catch this: the test harness
    doesn't enforce Android's real network-security policy, so a wrong
    *scheme* was invisible there — only a real device surfaces it,
    which is exactly how this second bug was actually found.
    """
    if not url:
        return ""
    absolute = request.build_absolute_uri(url)
    if request.META.get("HTTP_X_FORWARDED_PROTO") == "https" and absolute.startswith("http://"):
        absolute = "https://" + absolute[len("http://"):]
    return absolute
