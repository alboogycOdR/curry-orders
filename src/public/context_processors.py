"""Template context processors for the `public` app.

`v2_shell`: gives every `/v2/` page the poster variant's chrome data
(site name, contact phone) regardless of which view renders it —
`views_v2.home`/`checkout` already build this themselves, but
`views_v2.order_status`/`lookup` delegate straight to the *Broadsheet*
view functions in `views.py` (parametrised by `template_name` so the
query/business logic isn't duplicated — see that module), which have no
reason to know about /v2/'s shell context. Rather than threading an
`extra_context` kwarg through every delegated view, this processor
gives base_v2.html what it needs no matter which view produced the
response, and costs nothing on any other route (the path check is
first, before the one Settings query it guards).
"""
from __future__ import annotations

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
    if not request.path.startswith("/v2/"):
        return {}
    settings = Settings.current()
    phone_e164 = settings.support_whatsapp_e164
    return {
        "site_name": settings.public_site_name or "Roti Connect",
        "contact_phone_e164": phone_e164,
        "contact_phone_display": _whatsapp_display(phone_e164),
    }
