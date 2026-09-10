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
    """Poster-variant home (hero/collection-info/menu-teaser/promise/
    steps/final-CTA). Matches the *Broadsheet* home's own information
    architecture (views.home()) — Home is a read-only landing page; it
    has never had slot-picking (that's Basket's job alone, both here and
    on the Broadsheet site). The design guide's original single-page
    mockup put a slot picker in its Home hero section; this build moved
    it to the real Basket page instead once the 2025-09 IA review
    compared the two surfaces side by side and found Home picking slots
    was a poster-only invention with no equivalent on the site it's
    meant to be compared against.

    The /v2/ shell context (site_name, contact phone) doesn't need
    building here — `public.context_processors.v2_shell` supplies it to
    every /v2/ template automatically.
    """
    settings = Settings.current()
    today = now_sast().date()
    days = public_views._orderable_day_list(today, settings)
    first_day = _first_orderable_day(days)

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


def basket(request: HttpRequest) -> HttpResponse:
    """Poster-variant Basket — a real page (information-architecture
    parity with the Broadsheet site: Basket has always been its own
    screen there, with the day/slot picker, editable lines and Continue
    button views.basket()/basket.js already implement — reused verbatim,
    including edit-mode via the item-configurator sheet)."""
    return public_views.basket(request, template_name="public/v2/basket.html")


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


def account(request: HttpRequest) -> HttpResponse:
    return public_views.account(request, template_name="public/v2/account.html")


def customer_login(request: HttpRequest) -> HttpResponse:
    return public_views.customer_login(
        request, template_name="public/v2/customer_login.html", redirect_namespace="v2",
    )


def customer_signup(request: HttpRequest) -> HttpResponse:
    return public_views.customer_signup(
        request, template_name="public/v2/customer_signup.html", redirect_namespace="v2",
    )


def account_setup(request: HttpRequest) -> HttpResponse:
    return public_views.account_setup(
        request, template_name="public/v2/account_setup.html", redirect_namespace="v2",
    )


def help_page(request: HttpRequest) -> HttpResponse:
    return public_views.help_page(request, template_name="public/v2/help.html")


def policies_page(request: HttpRequest) -> HttpResponse:
    return public_views.policies_page(request, template_name="public/v2/policies.html")


def reorder(request: HttpRequest, public_token: str) -> HttpResponse:
    return public_views.reorder(
        request, public_token, template_name="public/v2/reorder.html", redirect_namespace="v2",
    )
