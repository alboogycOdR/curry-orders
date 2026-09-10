"""Template context processors for the `public` app.

`v2_shell`: gives every poster-variant page the shared chrome data (site
name, contact phone) regardless of which view renders it —
`views_v2.home`/`checkout` already build this themselves, but
`views_v2.order_status`/`lookup` delegate straight to the *Broadsheet*
view functions in `views.py` (parametrised by `template_name` so the
query/business logic isn't duplicated — see that module), which have no
reason to know about the poster variant's shell context. Rather than
threading an `extra_context` kwarg through every delegated view, this
processor gives base_v2.html what it needs no matter which view
produced the response.

Gated on `settings.ROOT_URLCONF`, not the request path: the poster
variant used to be a `/v2/` path prefix on the same service (checked via
`request.path.startswith("/v2/")`), but moved to its own standalone
deploy — docker-compose's `web-v2` service, its own port, `ROOT_URLCONF
=config.urls_v2_root` — because the shared-port prefix caused real
in-page navigation bugs (see config/urls_v2_root.py's own comment). A
path-prefix check silently stopped matching anything once that move
happened (found live: phone number and site name went missing from
every poster page, masked everywhere except the browser tab title by
that one spot's own `|default:` fallback) — checking which urlconf this
*process* is running under is correct regardless of deploy shape, and
was always the more direct condition (`web-v2` is defined entirely by
having a different urlconf; the port number is just how that's exposed).
"""
from __future__ import annotations

from django.conf import settings as django_settings
from django.http import HttpRequest

from core.models import Settings


def _whatsapp_display(e164: str | None) -> str | None:
    """Mirrors views_v2._whatsapp_display exactly — kept as one copy
    would create an import cycle (views_v2 -> context_processors ->
    views_v2); both are tiny and unlikely to diverge, but if you change
    one, change the other."""
    if not e164:
        return None
    national = e164.lstrip("+").replace("27", "0", 1)
    if len(national) != 10:
        return national
    return f"{national[0:3]} {national[3:6]} {national[6:10]}"


def v2_shell(request: HttpRequest) -> dict:
    if django_settings.ROOT_URLCONF != "config.urls_v2_root":
        return {}
    settings = Settings.current()
    phone_e164 = settings.support_whatsapp_e164
    return {
        "site_name": settings.public_site_name or "Roti Connect",
        "contact_phone_e164": phone_e164,
        "contact_phone_display": _whatsapp_display(phone_e164),
    }
