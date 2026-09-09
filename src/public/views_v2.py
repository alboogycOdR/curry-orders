"""Poster-variant customer views, served under /v2/ (namespace "v2").

Runs side by side with the Broadsheet customer surface in views.py — same
backend (capacity, checkout, order status, auth), different templates and
CSS only, per updates0909/handover_poster_variant/README.md. The two
surfaces are meant to be compared live before one is archived; neither
replaces the other yet (see CLAUDE.md).

Chunk 1 (this file): foundation only — the page shell (promo strip,
header, footer, bottom nav) via base_v2.html, and a placeholder home view.
Hero/collection/menu/basket/checkout/order-status land in later chunks,
reusing the same helpers already proven out in views.py (menu_queries,
_featured_dish, dish_photo_url, etc.) rather than duplicating them.
"""
from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from core.models import Settings


def _whatsapp_display(e164: str | None) -> str | None:
    """"+27826023031" -> "082 602 3031". Mirrors the "0" + national-number
    convention views.py's home()/order_status() already use for
    `whatsapp_number`, just grouped for display rather than left as one
    run of digits — the guide's promo strip/footer/header want the
    grouped form."""
    if not e164:
        return None
    national = e164.lstrip("+").replace("27", "0", 1)
    if len(national) != 10:
        return national
    return f"{national[0:3]} {national[3:6]} {national[6:10]}"


def _v2_shell_context() -> dict:
    """Context every /v2/ page needs for base_v2.html's chrome (promo
    strip, header, footer) — kept in one place so per-page views don't
    each re-derive it."""
    settings = Settings.current()
    phone_e164 = settings.support_whatsapp_e164
    return {
        "site_name": settings.public_site_name or "Roti Connect",
        "contact_phone_e164": phone_e164,
        "contact_phone_display": _whatsapp_display(phone_e164),
    }


def home(request: HttpRequest) -> HttpResponse:
    """Poster-variant home — single scrolling page (guide §8.1). Chunk 1:
    shell only, honest placeholder body (README's "no fake states" rule
    applies here too — this says it's unfinished rather than showing an
    empty or fabricated page)."""
    ctx = _v2_shell_context()
    return render(request, "public/v2/home.html", ctx)
