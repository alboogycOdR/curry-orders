"""Customer-facing views for the four Broadsheet screens (design handoff:
`updates/Curry orders modernization/design_handoff_brandons_kitchen/`)
plus the real `/menu` and `/dishes/:slug` pages spec §6.1/§11.3/§11.4
ask for (milestone 2).

Milestone 2 status: menu/dish/availability are real (`core.menu`,
backed by `core.Dish`/`core.DayDishAvailability`, sold-out states
computed via `core.capacity.dish_units_used`). Milestone 3 status:
**not started** — order creation, the reservation transaction, and
checkout are still client-side only. Two concessions worth flagging,
neither of which is what the eventual production build will do:

- The cart lives in the browser's `localStorage` (see `static/js/cart.js`),
  not a session or a draft `Order` row. The handoff's own "State" section
  names both as legitimate options for a prototype; a draft-Order-backed
  cart is the real milestone-3 design, once `core.capacity.reserve()`
  (already written, not yet wired to any view — see core/capacity.py's
  own module docstring) has a caller.
- Checkout's "confirmed" state is a same-page JS swap with a fabricated
  reference, not a real order. Nothing is written to the database on
  "Place the order" yet.
"""
from __future__ import annotations

import datetime as dt

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from core import menu as menu_queries
from core.capacity import OCCUPYING_STATUSES
from core.materialise import materialise_days
from core.models import Order, Settings, TradingDay
from core.tz import coerce_time, now_sast, orderable_dates

_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_DAY_NAMES_FULL = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
]
_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _orderable_day_list(today: dt.date, settings: Settings) -> list[dict]:
    """§11.3's "date switcher listing `orderable_dates` only" — real
    `core.tz.orderable_dates()` (D-05) against real `TradingDay` rows,
    lazily materialised first (§7.5: "when any code path needs a date
    inside the horizon and no row exists, insert one from settings
    defaults... and generate its slots") so this works even before the
    scheduler's own daily `materialise_days` tick has run.

    Same `{index, iso, dow, dom, long}` shape order.js/checkout.js
    already expect — `index` is now a position in the *orderable* list,
    not a literal day offset, since a closed day is simply absent rather
    than shown-and-disabled (spec's own "listing orderable_dates only").
    """
    trading_days_list = materialise_days(today, settings, count=settings.preorder_days + 1)
    trading_days = {td.date: td for td in trading_days_list}
    today_cutoff = coerce_time(trading_days[today].cutoff_time) if today in trading_days \
        else coerce_time(settings.same_day_cutoff)

    dates = orderable_dates(
        now_sast(),
        is_open=lambda d: trading_days.get(d).is_open if trading_days.get(d) else False,
        cutoff_time=today_cutoff,
        preorder_days=settings.preorder_days,
    )

    days = []
    for i, d in enumerate(dates):
        is_today = d == today
        dow = "Today" if is_today else _DAY_NAMES[d.weekday()]
        long_prefix = "today, " if is_today else ""
        # Deliberately lowercase-first when today ("today, Sat 29 Aug") —
        # matches the handoff's own `long` field; a stand-alone display
        # (order.js/checkout.js "chosenDay") title-cases it itself.
        long_label = f"{long_prefix}{_DAY_NAMES[d.weekday()]} {d.day} {_MONTH_NAMES[d.month - 1]}"
        days.append(
            {"index": i, "iso": d.isoformat(), "dow": dow, "dom": d.day, "long": long_label}
        )
    return days


def _slot_list_for_day(trading_day: TradingDay | None) -> tuple[list[str], list[str]]:
    """Real `Slot` rows for one trading day: `(all_labels, full_labels)`.
    `full_labels` is computed from actual occupying orders
    (`core.capacity.OCCUPYING_STATUSES`) — always empty right now since
    no order-creation flow exists yet (milestone 3), which is the
    correct, honest answer, not a placeholder.

    Only ever looks at *one* day (the soonest orderable one) — the
    order screen doesn't yet re-fetch slots when the customer picks a
    different day (that needs `GET /api/availability?date=`, real
    capacity-engine surface area, milestone 3); every materialised day
    shares the same default window today, so this is a visible
    simplification only once a specific day's window is customised.
    """
    if trading_day is None:
        return [], []
    slots = list(trading_day.slots.order_by("start_at"))
    labels = []
    full_labels = []
    for s in slots:
        label = s.start_at.strftime("%H:%M")
        labels.append(label)
        occupying = Order.objects.filter(slot=s, status__in=OCCUPYING_STATUSES).count()
        if s.is_closed or occupying >= s.capacity:
            full_labels.append(label)
    return labels, full_labels


def home(request: HttpRequest) -> HttpResponse:
    settings = Settings.current()
    cutoff = coerce_time(settings.same_day_cutoff)
    window_start = coerce_time(settings.default_window_start)
    window_end = coerce_time(settings.default_window_end)

    # The handoff's fixed "Today's picks" trio (README §2), now the real
    # dishes with those slugs if they exist — falls back to "however many
    # exist" rather than erroring pre-seed.
    pick_slugs = ("full-house-masala-steak-gatsby", "chicken-masala-roti-roll", "beef-lasagne")
    all_dishes = {d.slug: d for d in menu_queries.active_dishes()}
    picks = [
        {"dish": all_dishes[slug], "portion": all_dishes[slug].portion_label}
        for slug in pick_slugs if slug in all_dishes
    ]

    today = now_sast().date()
    full_weekday = _DAY_NAMES_FULL[today.weekday()]
    today_label = f"{full_weekday} {today.day} " + _MONTH_NAMES[today.month - 1]

    return render(request, "public/home.html", {
        "orders_per_day": settings.default_daily_order_cap,
        "slot_minutes": settings.slot_minutes,
        "same_day_cutoff": cutoff.strftime("%H:%M"),
        "collection_window": f"{window_start.strftime('%H:%M')}–{window_end.strftime('%H:%M')}",
        "picks": picks,
        "today_label": today_label,
    })


def menu(request: HttpRequest) -> HttpResponse:
    """§11.3: date switcher + dish cards, sold-out states, no cart
    interactivity — that's `/order/` (D-32). `?date=` selects which
    day's availability to show; defaults to the soonest orderable date.
    """
    settings = Settings.current()
    today = now_sast().date()
    days = _orderable_day_list(today, settings)

    date_param = request.GET.get("date")
    selected_iso = date_param if date_param in {d["iso"] for d in days} else (
        days[0]["iso"] if days else today.isoformat()
    )
    selected_date = dt.date.fromisoformat(selected_iso)
    trading_day = TradingDay.objects.filter(date=selected_date).first()

    dishes = menu_queries.dishes_for_date(trading_day) if trading_day else []
    categories = menu_queries.categories_ordered(dishes)

    return render(request, "public/menu.html", {
        "days": days,
        "selected_iso": selected_iso,
        "categories": categories,
    })


def dish_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """§11.4: gallery (none yet — no dish photos exist pre-seed, same
    honest "text-only for now" state the handoff's own menu screen
    already carries), description, portion, allergens, price, options,
    qty stepper, Add to cart. `?date=` (permalinks carry it, §6.1)
    selects which day's sold-out state to show, clamped to the horizon;
    "Add to cart" itself still goes through the shared client-side cart
    (dish.js/cart.js) regardless of date — a real per-date re-validation
    of the *cart* (not just this page) is milestone 3's "changing date
    re-validates every line" (§11.4).
    """
    dish = menu_queries.dish_by_slug(slug)
    if dish is None or dish.archived_at is not None:
        raise Http404("No such dish.")

    settings = Settings.current()
    today = now_sast().date()
    date_param = request.GET.get("date")
    try:
        selected_date = dt.date.fromisoformat(date_param) if date_param else today
    except ValueError:
        selected_date = today
    # Clamp to the horizon before materialising anything — an arbitrary
    # `?date=` on a public GET request must not be able to make this
    # view insert TradingDay rows without bound.
    if not (today <= selected_date <= today + dt.timedelta(days=settings.preorder_days)):
        selected_date = today
    trading_day = materialise_days(selected_date, settings, count=1)[0]

    sold_out = False
    for menu_dish in menu_queries.dishes_for_date(trading_day):
        if menu_dish.id == dish.pk:
            sold_out = menu_dish.sold_out
            break

    options = menu_queries.dish_options(dish)
    return render(request, "public/dish_detail.html", {
        "dish": dish,
        "options": options,
        "sold_out": sold_out,
    })


def order(request: HttpRequest) -> HttpResponse:
    settings = Settings.current()
    today = now_sast().date()
    days = _orderable_day_list(today, settings)
    first_day = TradingDay.objects.filter(date=dt.date.fromisoformat(days[0]["iso"])).first() \
        if days else None
    slots, full_slots = _slot_list_for_day(first_day)

    dishes = menu_queries.dishes_for_date(first_day, with_options=True) if first_day else []
    categories = menu_queries.categories_ordered(dishes)

    return render(request, "public/order.html", {
        "categories": categories,
        "days": days,
        "slots": slots,
        "full_slots_today": full_slots,
    })


def checkout(request: HttpRequest) -> HttpResponse:
    settings = Settings.current()
    today = now_sast().date()
    return render(request, "public/checkout.html", {
        # Cart lines already carry {name, price} (cart.js), so checkout
        # doesn't need the menu price map — only the day list, to turn the
        # day index the order screen stored back into a display label.
        "days": _orderable_day_list(today, settings),
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
