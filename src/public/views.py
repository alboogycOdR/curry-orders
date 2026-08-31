"""Customer-facing views for the four Broadsheet screens (design handoff:
`updates/Curry orders modernization/design_handoff_brandons_kitchen/`)
plus the real `/menu`, `/dishes/:slug` and `/orders/:public_token` pages
spec §6.1/§11.3/§11.4/§11.7-9 ask for.

Milestone 2 status: menu/dish/availability are real (`core.menu`,
backed by `core.Dish`/`core.DayDishAvailability`, sold-out states
computed via `core.capacity.dish_units_used`). Milestone 3 status:
checkout is real — "Place the order" (checkout.js) calls the real
`POST /api/checkout` (`public/api.py`), which runs `core.capacity.reserve()`
(§8.3's transaction) and creates a real `core.Order`; the customer is
handed off to this module's `order_status` view afterwards. Milestone 4
status: the EFT page is real too — `order_status` renders bank details,
a hold countdown and a working proof-upload control for
`awaiting_eft`/`payment_review` EFT orders (§11.7); uploads go through
`POST /api/orders/:token/proof` (`public/api.py`'s `upload_proof`,
`core.eft.record_proof_upload`). Still just the customer half — the
staff EFT queue that verifies/rejects a proof is milestone 5.

One concession still worth flagging, not what the eventual production
build will do:

- The cart lives in the browser's `localStorage` (see `static/js/cart.js`),
  not a session or a draft `Order` row — it's only ever a client-side
  staging area that gets turned into one real transaction at checkout,
  never partially persisted server-side before that. The handoff's own
  "State" section names both `localStorage` and a draft-Order as
  legitimate prototype options; nothing about the current design forces
  a move to the latter, but it remains open for a later pass (e.g. if
  cross-device cart recovery becomes a real requirement).
"""
from __future__ import annotations

import datetime as dt
import json

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from core import lookup as lookup_service
from core import menu as menu_queries
from core.capacity import OCCUPYING_STATUSES
from core.materialise import materialise_days
from core.models import (
    Customer,
    DishOptionValue,
    Order,
    OrderStatus,
    PaymentMethod,
    Settings,
    TradingDay,
)
from core.phone import InvalidPhoneNumber, normalize_sa_mobile
from core.tz import coerce_time, now_sast, orderable_dates

from . import customer_sessions

# §9.1's own note under the customer-copy table: "Collection address and
# instructions render only on confirmed_prep, cash_due, in_kitchen,
# ready." — reused by order_status below.
_ADDRESS_BEARING_STATUSES = frozenset({
    OrderStatus.CONFIRMED_PREP, OrderStatus.CASH_DUE, OrderStatus.IN_KITCHEN, OrderStatus.READY,
})
# §11.7: the EFT page (bank details, hold countdown, proof upload)
# only makes sense while payment is still outstanding.
_EFT_PAGE_STATUSES = frozenset({OrderStatus.AWAITING_EFT, OrderStatus.PAYMENT_REVIEW})

# §11.7-9's plain-language status copy — not the internal state-machine
# name (OrderStatus's own label is closer to a kitchen-desk word than
# something to put in front of a customer, e.g. "confirmed_prep").
_STATUS_COPY: dict[str, str] = {
    OrderStatus.AWAITING_EFT: "Awaiting your EFT payment.",
    OrderStatus.PAYMENT_REVIEW: "Payment received — a staff member is confirming it.",
    OrderStatus.CONFIRMED_PREP: "Confirmed — going into prep before your slot.",
    OrderStatus.CASH_REQUEST: "Awaiting kitchen confirmation for cash on collection.",
    OrderStatus.CASH_DUE: "Confirmed — bring cash at collection.",
    OrderStatus.IN_KITCHEN: "In the kitchen now.",
    OrderStatus.READY: "Ready for collection.",
    OrderStatus.COLLECTED: "Collected — thank you!",
    OrderStatus.PAYMENT_EXPIRED: "This order's payment window expired and the hold was released.",
    OrderStatus.CANCELLED: "This order was cancelled.",
}

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


def _slot_list_for_day(trading_day: TradingDay | None) -> list[dict]:
    """Real `Slot` rows for one trading day, each `{id, label, full}` —
    `id` is the real `Slot` PK the checkout API needs (§17.3's
    `POST /api/checkout` body takes `slot_id`, not a time label); `full`
    is computed from actual occupying orders
    (`core.capacity.OCCUPYING_STATUSES`).

    Only ever looks at *one* day (the soonest orderable one) — the order
    screen doesn't yet re-fetch slots when the customer picks a different
    day (that needs `GET /api/availability?date=`, still-unbuilt
    optimistic-read surface area — checkout itself re-validates
    everything server-side regardless, per §8.6); every materialised day
    shares the same default window today, so this is a visible
    simplification only once a specific day's window is customised.
    """
    if trading_day is None:
        return []
    slots = list(trading_day.slots.order_by("start_at"))
    result = []
    for s in slots:
        occupying = Order.objects.filter(slot=s, status__in=OCCUPYING_STATUSES).count()
        result.append({
            "id": s.pk,
            "label": s.start_at.strftime("%H:%M"),
            "full": s.is_closed or occupying >= s.capacity,
        })
    return result


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
    slots = _slot_list_for_day(first_day)

    dishes = menu_queries.dishes_for_date(first_day, with_options=True) if first_day else []
    categories = menu_queries.categories_ordered(dishes)

    settings = Settings.current()
    return render(request, "public/order.html", {
        "categories": categories,
        "days": days,
        "slots": slots,
        "eft_hold_minutes": settings.eft_hold_minutes,
    })


def checkout(request: HttpRequest) -> HttpResponse:
    """§20's own acceptance line "cash hidden on advance dates and when
    cap reached" — `cash_daily_cap` is a *count* of cash orders per day
    (`core.capacity.check_cash`), not a rand figure, so `cash_remaining`
    is a live count too. `checkout.js` hides the cash option itself once
    the customer's chosen day isn't `today_iso`, or once
    `cash_available` is false; `reserve()` re-checks all of this
    server-side regardless (§8.6), same as every other client-side
    convenience check in this app.
    """
    settings = Settings.current()
    today = now_sast().date()
    trading_day = materialise_days(today, settings, count=1)[0]
    cash_occupying_today = Order.objects.filter(
        trading_day=trading_day, payment_method=PaymentMethod.CASH, status__in=OCCUPYING_STATUSES,
    ).count()
    cash_remaining = max(0, settings.cash_daily_cap - cash_occupying_today)

    return render(request, "public/checkout.html", {
        # Cart lines already carry {name, price} (cart.js), so checkout
        # doesn't need the menu price map — only the day list, to turn the
        # day index the order screen stored back into a display label.
        "days": _orderable_day_list(today, settings),
        "eft_hold_minutes": settings.eft_hold_minutes,
        "today_iso": today.isoformat(),
        "cash_available": settings.cash_enabled and cash_remaining > 0,
        "cash_remaining": cash_remaining,
    })


def order_status(request: HttpRequest, public_token: str) -> HttpResponse:
    """Spec §6.1 `/orders/:public_token` — order status view,
    `noindex, nofollow`. Not one of the four handoff screens: order
    number, status in plain language, the order sheet, collection
    details, and — for an EFT order still `awaiting_eft`/`payment_review`
    (§11.7) — bank details, a hold countdown and the proof-upload
    control (`static/js/eft.js`). The staff side that verifies/rejects a
    proof (the EFT queue) is milestone 5; a payment_review order here
    just says "we're checking it" until then.
    """
    order = Order.objects.filter(public_token=public_token).select_related(
        "trading_day", "slot", "payment",
    ).prefetch_related("lines").first()
    if order is None:
        raise Http404("No such order.")

    show_eft_panel = (
        order.payment_method == PaymentMethod.EFT and order.status in _EFT_PAGE_STATUSES
    )

    return render(request, "public/order_status.html", {
        "order": order,
        "lines": order.lines.all(),
        "status_copy": _STATUS_COPY.get(order.status, order.get_status_display()),
        "show_address": order.status in _ADDRESS_BEARING_STATUSES,
        "show_eft_panel": show_eft_panel,
        # collection_address_line/instructions (show_address) and the
        # bank fields (show_eft_panel) are disjoint statuses (§9.1's
        # customer-copy note vs §11.7) but both come off the one
        # Settings row — fetched once regardless of which panel needs it.
        "settings": Settings.current(),
        "proof_already_uploaded": (
            bool(order.payment.proof_uploaded_at) if show_eft_panel else False
        ),
        # §11.11: "Order these again" only on a collected order's page.
        "can_reorder": order.status == OrderStatus.COLLECTED,
    })


# ---------------------------------------------------------------- lookup (§11.10)


_LOOKUP_GENERIC_ERROR = (
    "We couldn't find a matching order. Check your order number and mobile number."
)


def lookup(request: HttpRequest) -> HttpResponse:
    """§11.10: order number (`CT-…`, case-insensitive) + mobile (any
    accepted format, matched on the last 9 digits of the stored E.164
    number). Throttled 10/hour/IP and 10/hour/order number
    (`core.lookup`, reusing M7's `throttle_events` table); every failure
    — throttled, no such order, wrong mobile — renders the exact same
    generic message, so this page can never be used to enumerate real
    order numbers or confirm a guessed mobile number against one.
    """
    error = None
    order_number_input = ""
    if request.method == "POST":
        order_number_input = str(request.POST.get("order_number", ""))
        mobile_input = str(request.POST.get("mobile", ""))
        ip = request.META.get("REMOTE_ADDR") or "unknown"

        try:
            lookup_service.check_lookup_throttle(ip, order_number_input)
        except lookup_service.LookupError:
            error = _LOOKUP_GENERIC_ERROR
        else:
            order = lookup_service.find_order(order_number_input, mobile_input)
            lookup_service.record_lookup_attempt(ip, order_number_input)
            if order is None:
                error = _LOOKUP_GENERIC_ERROR
            else:
                response = redirect("public:order_status", public_token=order.public_token)
                # §11.10: "set a 24h httpOnly cookie scoped to that token".
                response.set_cookie(
                    f"order_auth_{order.public_token}",
                    "1",
                    max_age=24 * 60 * 60,
                    httponly=True,
                    samesite="Lax",
                    secure=request.is_secure(),
                )
                return response

    return render(request, "public/lookup.html", {
        "error": error,
        "order_number": order_number_input,
    })


def account(request: HttpRequest) -> HttpResponse:
    return render(request, "public/account.html")


def customer_login(request: HttpRequest) -> HttpResponse:
    error = None
    if request.method == "POST":
        try:
            mobile = normalize_sa_mobile(str(request.POST.get("mobile", "")))
        except InvalidPhoneNumber:
            mobile = ""
        password = str(request.POST.get("password", ""))
        customer = Customer.objects.filter(mobile_e164=mobile, anonymised_at__isnull=True).first()
        if (
            not customer
            or not customer.password_hash
            or not check_password(password, customer.password_hash)
        ):
            error = "We couldn't sign you in. Check your mobile number and password."
        else:
            customer_sessions.log_in(request, customer)
            return redirect("public:account")
    return render(request, "public/customer_login.html", {"error": error})


def customer_signup(request: HttpRequest) -> HttpResponse:
    error = None
    if request.method == "POST":
        name = str(request.POST.get("name", "")).strip()
        raw_mobile = str(request.POST.get("mobile", ""))
        password = str(request.POST.get("password", ""))
        try:
            mobile = normalize_sa_mobile(raw_mobile)
        except InvalidPhoneNumber:
            mobile = ""
            error = "Enter a valid South African mobile number."
        if not error and len(name) < 2:
            error = "Enter your name."
        if not error and len(password) < 8:
            error = "Use at least 8 characters for your password."
        if not error:
            customer, _ = Customer.objects.get_or_create(
                mobile_e164=mobile, defaults={"full_name": name}
            )
            if customer.password_hash:
                error = "An account already exists for that mobile number."
            else:
                customer.full_name = name
                customer.password_hash = make_password(password)
                customer.save(update_fields=["full_name", "password_hash"])
                customer_sessions.log_in(request, customer)
                return redirect("public:account")
    return render(request, "public/customer_signup.html", {"error": error})


def customer_logout(request: HttpRequest) -> HttpResponse:
    customer_sessions.log_out(request)
    return redirect("public:account")


# ---------------------------------------------------------------- reorder (§11.11)


def reorder(request: HttpRequest, public_token: str) -> HttpResponse:
    """§11.11: on a `collected` order's page, "Order these again" seeds a
    fresh cart from the same lines, at *current* prices — never the
    original order's snapshot — dropping any line whose dish has since
    been archived or deactivated (listed in a notice on this page).
    Option selections are best-effort re-matched by (option name, value
    name) against the dish's *current* options; a selection that no
    longer has a live match is simply dropped from that line rather than
    blocking the whole line — the customer can re-pick it on `/order/`.
    The new cart is seeded into the shared client-side cart
    (`static/js/cart.js`) exactly like `dish.js` does; date/slot/payment
    are then chosen afresh on `/order/` → `/checkout/`, same as any
    other cart.
    """
    order = Order.objects.filter(public_token=public_token).prefetch_related(
        "lines__dish__options__values",
    ).first()
    if order is None:
        raise Http404("No such order.")
    if order.status != OrderStatus.COLLECTED:
        messages.error(request, "Only a collected order can be reordered.")
        return redirect("public:order_status", public_token=public_token)

    kept: dict[str, dict[str, object]] = {}
    dropped: list[str] = []
    for line in order.lines.all():
        dish = line.dish
        if dish is None or dish.archived_at is not None or not dish.is_active_on_menu:
            dropped.append(line.dish_name_snapshot)
            continue

        matched_values = []
        for selection in line.options_snapshot:
            match = DishOptionValue.objects.filter(
                option__dish=dish,
                option__name=selection.get("option"),
                name=selection.get("value"),
                is_available=True,
            ).first()
            if match is not None:
                matched_values.append(match)

        option_ids = sorted({v.pk for v in matched_values})
        composite_id = (
            f"{dish.pk}:{','.join(str(i) for i in option_ids)}" if option_ids else str(dish.pk)
        )
        unit_price_cents = dish.price_cents + sum(v.price_delta_cents for v in matched_values)
        name_suffix = (
            " (" + ", ".join(v.name for v in matched_values) + ")" if matched_values else ""
        )

        entry = kept.setdefault(composite_id, {
            "name": dish.name + name_suffix, "price": unit_price_cents, "qty": 0,
        })
        entry["qty"] = int(entry["qty"]) + line.quantity

    if not kept:
        messages.error(request, "None of this order's dishes are still available to reorder.")
        return redirect("public:order_status", public_token=public_token)

    return render(request, "public/reorder.html", {
        "order": order,
        "dropped": dropped,
        # `</script>`-safe: a dish name is manager-entered, not
        # untrusted, but there's no reason to trust it not to contain
        # that literal substring either.
        "cart_json": json.dumps(kept).replace("</", "<\\/"),
    })


# ---------------------------------------------------------------- help / policies (§11.12)


def help_page(request: HttpRequest) -> HttpResponse:
    """§6.1's `/help`: "how to order, collection, payment, cut-off" —
    every figure here is a live `Settings` value, not hard-coded copy,
    so a settings change (§20's own acceptance line: "cut-off, hold
    minutes, ... editable without deploy") is reflected here without a
    second place to update.
    """
    settings = Settings.current()
    return render(request, "public/help.html", {
        "same_day_cutoff": coerce_time(settings.same_day_cutoff).strftime("%H:%M"),
        "preorder_days": settings.preorder_days,
        "slot_minutes": settings.slot_minutes,
        "collection_window": (
            f"{coerce_time(settings.default_window_start).strftime('%H:%M')}"
            f"–{coerce_time(settings.default_window_end).strftime('%H:%M')}"
        ),
        "eft_hold_minutes": settings.eft_hold_minutes,
        "cash_enabled": settings.cash_enabled,
        "cash_same_day_only": settings.cash_same_day_only,
        "support_whatsapp_e164": settings.support_whatsapp_e164,
    })


def policies_page(request: HttpRequest) -> HttpResponse:
    """§6.1's `/policies`: cancellation (§19), allergens/home-kitchen
    (owner wording — `Settings.allergen_disclaimer`/`home_kitchen_notice`,
    both still unset per §23's own owner-input table; rendered with a
    plain "not yet provided" fallback rather than inventing wording on
    the owner's behalf), and the POPIA notice §11.12 spells out
    verbatim (what's stored, purpose, retention, deletion, and the
    Finland-hosting/POPIA line).
    """
    settings = Settings.current()
    return render(request, "public/policies.html", {
        "settings": settings,
        "proof_retention_days": settings.proof_retention_days,
        "order_retention_months": settings.order_retention_months,
        "support_whatsapp_e164": settings.support_whatsapp_e164,
    })


def robots_txt(request: HttpRequest) -> HttpResponse:
    """§6.1's `/robots.txt`, §21 go-live item 7 ("robots.txt and noindex
    verified with a crawler check"). Belt-and-braces alongside the
    per-page `<meta name="robots">` tags (`/orders/*`, `/lookup/`) and the
    `X-Robots-Tag` header (`staff/middleware.py`, everything under
    `/manage/`) — a compliant crawler honours whichever of the three it
    sees first, and this is the one checked before the crawler has
    fetched a single page.

    Only the pages spec §6.1's own sitemap line names (`/`, `/menu`,
    `/dishes/*`, `/help`, `/policies`) are crawlable; everything
    transactional or staff-only is disallowed explicitly rather than
    relying on `noindex` alone to keep it out of search results.
    """
    lines = [
        "User-agent: *",
        "Disallow: /order/",
        "Disallow: /checkout/",
        "Disallow: /orders/",
        "Disallow: /lookup/",
        "Disallow: /manage/",
        "Disallow: /admin/",
        "Disallow: /healthz",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
