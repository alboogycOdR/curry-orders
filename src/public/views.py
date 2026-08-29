"""Customer-facing views for the four Broadsheet screens (design handoff:
`updates/Curry orders modernization/design_handoff_brandons_kitchen/`).

This is the **visual** pass only — recreating the four screens as Django
templates against the design system, per the owner's steer this session.
None of these views touch the capacity engine, order creation, or payment
(`core.capacity`/`core.transitions` don't exist yet — those are milestones
2-7, spec §22). Where the handoff's sample data would in production be a
live query (slot availability, the cash cap remaining, the kitchen run
sheet), that's called out inline with which milestone owns it.

Two client-side-only concessions worth flagging up front, since neither
one is what the eventual production build will do:

- The cart lives in the browser's `localStorage` (see `static/js/cart.js`),
  not a session or a draft `Order` row. The handoff's own "State" section
  names both as legitimate options for a prototype; a draft-Order-backed
  cart is the real milestone-3 design, once `core.capacity.reserve()`
  exists to hold it against a slot.
- Checkout's "confirmed" state is a same-page JS swap with a fabricated
  reference, not a real order. Nothing is written to the database on
  "Place the order" yet.
"""
from __future__ import annotations

import datetime as dt

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from core.models import Settings
from core.tz import coerce_time, now_sast

from . import sample_menu

_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _day_list(today: dt.date, count: int = 7) -> list[dict]:
    """Seven consecutive SAST calendar dates starting today, in the shape
    the order/checkout templates and `order.js` need for the day picker.

    This does **not** consult `trading_days`/`core.tz.orderable_dates` —
    there's no seeded `TradingDay` data yet (materialisation is the other
    half of milestone 1, not built this pass), and the handoff's own day
    picker is sample data ("in production this is a capacity query" —
    README §2). Swap this for `orderable_dates(now_sast(), is_open=...,
    ...)` once trading-day materialisation lands.
    """
    days = []
    for i in range(count):
        d = today + dt.timedelta(days=i)
        dow = "Today" if i == 0 else _DAY_NAMES[d.weekday()]
        long_prefix = "today, " if i == 0 else ""
        # Deliberately lowercase-first when i==0 ("today, Sat 29 Aug") —
        # matches the handoff's own `long` field exactly; callers that
        # display this stand-alone (order.js/checkout.js "chosenDay") title-
        # case it themselves, same as the handoff's `chosenDay` transform.
        long_label = f"{long_prefix}{_DAY_NAMES[d.weekday()]} {d.day} {_MONTH_NAMES[d.month - 1]}"
        days.append({
            "index": i,
            "iso": d.isoformat(),
            "dow": dow,
            "dom": d.day,
            "long": long_label,
        })
    return days


def _slot_list(settings: Settings) -> list[str]:
    """15-minute labels across the day's collection window, from Settings
    (falling back to the model defaults 16:00-18:00/15 min — §7.2) rather
    than the handoff's hard-coded eight strings, per §10's generation rule:
    start at `window_start`, emit `[t, t+slot_minutes)` while it still fits
    before `window_end`. Which of these are *full* is still sample data
    (see order.html/order.js) — that's a real capacity query, milestone 3.
    """
    start = coerce_time(settings.default_window_start)
    end = coerce_time(settings.default_window_end)
    minutes = settings.slot_minutes
    labels = []
    cur = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute
    while cur + minutes <= end_minutes:
        labels.append(f"{cur // 60:02d}:{cur % 60:02d}")
        cur += minutes
    return labels


def home(request: HttpRequest) -> HttpResponse:
    settings = Settings.current()
    cutoff = coerce_time(settings.same_day_cutoff)
    window_start = coerce_time(settings.default_window_start)
    window_end = coerce_time(settings.default_window_end)
    picks_ids = ("fh", "crr", "bl")  # the handoff's fixed "Today's picks" — copy to keep verbatim
    picks = []
    for cat in sample_menu.MENU:
        for dish in cat.dishes:
            if dish.id in picks_ids:
                picks.append({"dish": dish, "portion": cat.portion})
    picks.sort(key=lambda p: picks_ids.index(p["dish"].id))

    today = now_sast().date()
    # Handoff shows "Saturday 29 August" — full weekday name, unlike the
    # three-letter form the order/checkout day picker uses (_DAY_NAMES).
    full_weekday = [
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    ][today.weekday()]
    today_label = f"{full_weekday} {today.day} " + _MONTH_NAMES[today.month - 1]

    return render(request, "public/home.html", {
        "orders_per_day": settings.default_daily_order_cap,
        "slot_minutes": settings.slot_minutes,
        "same_day_cutoff": cutoff.strftime("%H:%M"),
        "collection_window": f"{window_start.strftime('%H:%M')}–{window_end.strftime('%H:%M')}",
        "picks": picks,
        "today_label": today_label,
    })


def order(request: HttpRequest) -> HttpResponse:
    settings = Settings.current()
    today = now_sast().date()
    return render(request, "public/order.html", {
        "menu": sample_menu.as_context(),
        "menu_price_map": sample_menu.as_price_map(),
        "days": _day_list(today),
        "slots": _slot_list(settings),
        # Sample-only: the handoff hard-codes these two 16:00-window slots
        # full for *today* to show the inert/line-through state; a real
        # capacity query (milestone 3, §8) replaces this entirely.
        "full_slots_today": ["16:30", "17:00"],
    })


def checkout(request: HttpRequest) -> HttpResponse:
    today = now_sast().date()
    return render(request, "public/checkout.html", {
        # Cart lines already carry {name, price} (cart.js), so checkout
        # doesn't need the menu price map — only the day list, to turn the
        # day index the order screen stored back into a display label.
        "days": _day_list(today),
        # Sample-only (milestone 3/7, D-06/§8.2's cash ceiling) — the
        # remaining daily cash allowance is a live aggregate over today's
        # occupying cash orders, not a constant.
        "cash_left": "R 180.00",
    })


def order_status(request: HttpRequest, public_token: str) -> HttpResponse:
    # Spec §6.1 `/orders/:public_token` — order status / EFT instructions /
    # confirmed view, `noindex, nofollow`. Not one of the four handoff
    # screens; still a placeholder pending milestone 4 (EFT page) and the
    # `core.Order` lookup-by-token it depends on.
    return HttpResponse(
        f"public:order_status placeholder for {public_token!r} — see spec §11.7-9, milestone 4"
    )
