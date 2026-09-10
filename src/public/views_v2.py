"""Poster-variant customer views, served under /v2/ (namespace "v2").

Runs side by side with the Broadsheet customer surface in views.py — same
backend (capacity, checkout, order status, auth), different templates and
CSS only, per updates0909/handover_poster_variant/README.md. The two
surfaces are meant to be compared live before one is archived; neither
replaces the other yet (see CLAUDE.md).

Reuse, not duplication: every view here either calls the exact same
`core`/`public.views` helpers the Broadsheet views use, or (checkout,
order_status, lookup) calls the *same view function* in views.py with a
different `template_name`/namespace kwarg — see that module for the
parametrisation. The two surfaces should only ever differ visually.
"""
from __future__ import annotations

import datetime as dt
import json

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from core import menu as menu_queries
from core.models import Settings, TradingDay
from core.tz import coerce_time, now_sast
from public import views as public_views


def _first_orderable_day(days: list[dict]) -> TradingDay | None:
    if not days:
        return None
    return TradingDay.objects.filter(date=dt.date.fromisoformat(days[0]["iso"])).first()


def _featured_context(request: HttpRequest, dishes: list) -> dict:
    """Featured dish for the hero — real MenuDish (with photo/sold_out),
    looked up by slug against whatever `active_dishes()`/`_featured_dish`
    (views.py's own selection logic, reused rather than re-implemented)
    picked."""
    active = menu_queries.active_dishes()
    featured_dish = public_views._featured_dish(active, request.GET.get("featured"))
    if featured_dish is None:
        return {"featured": None}
    return {"featured": next((d for d in dishes if d.slug == featured_dish.slug), None)}


def home(request: HttpRequest) -> HttpResponse:
    """Poster-variant home (guide §8.1's hero/collection/promise/steps/
    CTA sections). The full dish catalog moved to its own screen
    (`menu()`, split from home per the 2025-09 navigation review — a
    single scrolling page read as "the menu is stuck inside the home
    page" rather than a real Menu destination) — home only needs the one
    featured dish for its hero, not the whole catalog.

    The /v2/ shell context (site_name, contact phone) doesn't need
    building here — `public.context_processors.v2_shell` supplies it to
    every /v2/ template automatically.
    """
    settings = Settings.current()
    today = now_sast().date()
    days = public_views._orderable_day_list(today, settings)
    first_day = _first_orderable_day(days)
    slots = public_views._slot_list_for_day(first_day)

    # Only the featured dish's own data is needed here — with_options is
    # for the item-configurator sheet, which lives on the Menu page now.
    dishes = menu_queries.dishes_for_date(first_day, with_options=False) if first_day else []

    edition_label = ""
    if days:
        d = dt.date.fromisoformat(days[0]["iso"])
        edition_label = f"{public_views._DAY_NAMES[d.weekday()]} {d.day} {public_views._MONTH_NAMES[d.month - 1]}"

    # Same "Order by HH:MM" / "Ordering for <day>" split as views.home().
    cutoff = coerce_time(settings.same_day_cutoff)
    today_orderable = bool(days) and days[0]["iso"] == today.isoformat()
    cutoff_copy = (
        f"Order by {cutoff.strftime('%H:%M')}"
        if today_orderable
        else f"Ordering for {edition_label}" if edition_label else f"Order by {cutoff.strftime('%H:%M')}"
    )

    ctx: dict = {
        "days": days,
        "slots": slots,
        "edition_label": edition_label,
        "cutoff_copy": cutoff_copy,
        "today_orderable": today_orderable,
        "collection_window": (
            f"{coerce_time(first_day.window_start).strftime('%H:%M')}–"
            f"{coerce_time(first_day.window_end).strftime('%H:%M')}"
            if first_day else ""
        ),
        "collection_address_line": settings.collection_address_line,
        "eft_hold_minutes": settings.eft_hold_minutes,
    }
    ctx.update(_featured_context(request, dishes))
    return render(request, "public/v2/home.html", ctx)


def menu(request: HttpRequest) -> HttpResponse:
    """Poster-variant Menu — its own screen (split from home, see that
    view's docstring). Category filters + every real dish, add/qty via
    the item-configurator sheet (_item_sheet_v2.html/item-sheet.js,
    reused verbatim). No slot picker here — Collection stays the one
    place that sets it (guide's own collection-panel ownership of that
    control), so a visitor who lands on Menu first sees a banner
    pointing back to it rather than a second, possibly-drifting picker.
    """
    settings = Settings.current()
    today = now_sast().date()
    days = public_views._orderable_day_list(today, settings)
    first_day = _first_orderable_day(days)

    dishes = menu_queries.dishes_for_date(first_day, with_options=True) if first_day else []
    categories = menu_queries.categories_ordered(dishes)

    ctx: dict = {
        "categories": categories,
        "eft_hold_minutes": settings.eft_hold_minutes,
        "menu_catalog_json": json.dumps(
            public_views._menu_catalog_payload(dishes)
        ).replace("</", "<\\/"),
    }
    ctx.update(_featured_context(request, dishes))
    return render(request, "public/v2/menu.html", ctx)


def checkout(request: HttpRequest) -> HttpResponse:
    return render(request, "public/v2/checkout.html", public_views._checkout_context())


def order_status(request: HttpRequest, public_token: str) -> HttpResponse:
    # Delegates straight to the Broadsheet view's own query/context — it
    # already takes a template_name kwarg for exactly this. The /v2/ shell
    # context (site_name, phone) reaches base_v2.html via
    # public.context_processors.v2_shell regardless of which view renders
    # the response, so nothing extra is needed here.
    return public_views.order_status(
        request, public_token, template_name="public/v2/order_status.html",
    )


def lookup(request: HttpRequest) -> HttpResponse:
    return public_views.lookup(
        request, template_name="public/v2/lookup.html", status_namespace="v2",
    )
