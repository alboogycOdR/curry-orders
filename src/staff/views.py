"""Staff-facing views: auth (login/logout/change-password), the
owner-only settings editor, and the three real boards this project has
so far — the EFT payment queue (milestone 5), and the kitchen desk +
collection board (milestone 6). `public/views.py`'s "visual pass"
framing no longer applies to any of the three; the kitchen desk's old
sample run sheet/meters (design handoff README §4) are gone, replaced
by real `core.Order` aggregates.

Auth is `staff.sessions`, not `django.contrib.auth` — see that module's
docstring and `docs/DECISIONS.md` D-33 for why.

All three boards are real: real `core.Order` rows, real actions
(`core.transitions.apply()`, via `staff/api.py`'s transition endpoint
and its two day-level siblings). Kitchen/collection cover exactly
§9.3's board membership and §12.4/§12.5's acceptance items (summary
grouping, exceptions band, added-after-lock, lock prep list, mark
ready/collected, uncollect, close out day) — everything else in
`core/transitions.py` that isn't reachable from one of these three
boards (cash accept/reject, `change_slot`, `amend_items`) is still
real and tested, just unwired, waiting for milestone 7/9's board.
"""
from __future__ import annotations

import datetime as dt
from urllib.parse import urlencode

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.forms.models import model_to_dict
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from core.auth import (
    hash_password,
    is_locked_out,
    register_failed_login,
    register_successful_login,
    verify_password,
)
from core.capacity import (
    OCCUPYING_STATUSES,
    CapacityError,
    CheckoutLine,
    ReservationRequest,
    dish_units_used,
    reserve,
)
from core.materialise import materialise_day, materialise_days
from core.menu import active_dishes, dishes_for_date
from core.models import (
    ActorKind,
    DayDishAvailability,
    Dish,
    DishOption,
    DishOptionValue,
    Media,
    MediaKind,
    Order,
    OrderSource,
    OrderStatus,
    PaymentMethod,
    Settings,
    SettingsEvent,
    Slot,
    TradingDay,
    User,
)
from core.phone import InvalidPhoneNumber, normalize_sa_mobile
from core.transitions import Actor, TransitionError
from core.transitions import apply as apply_transition
from core.tz import SAST, coerce_time, now_sast
from storage.service import (
    InvalidUpload,
    sha256_digest,
    store_dish_image_bytes,
    validate_dish_image,
)

from . import sessions
from .decorators import owner_required, staff_login_required
from .forms import (
    ChangePasswordForm,
    DishForm,
    DishOptionForm,
    DishOptionValueForm,
    LoginForm,
    SettingsForm,
    TradingDayForm,
)

# Assisted orders (§12.9) are staff placing an order *on behalf of* a
# customer who phoned, walked in, or messaged — never the customer's own
# website checkout, which is always OrderSource.WEBSITE.
ASSISTED_SOURCES = frozenset({
    OrderSource.PHONE, OrderSource.IN_PERSON, OrderSource.WHATSAPP_ASSISTED,
})

_DAY_NAMES_FULL = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
]
_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


# ---------------------------------------------------------------- auth


def _safe_next(request: HttpRequest, candidate: str | None) -> str:
    """Validated `?next=` redirect target, same defence Django's own
    `LoginView` uses (`url_has_allowed_host_and_scheme` — refuses an
    off-site or scheme-relative URL) so a crafted `?next=` can't turn the
    login page into an open redirect. Falls back to the inbox (§12.2's
    "staff landing page"), now that it's a real screen (M9).
    """
    default = reverse("manage:inbox")
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return default


def login(request: HttpRequest) -> HttpResponse:
    if request.staff_user is not None:
        return redirect(_safe_next(request, request.GET.get("next")))

    error = None
    form = LoginForm(request.POST) if request.method == "POST" else LoginForm()

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        now = timezone.now()

        user = User.objects.filter(email=email, active=True).first()
        if user is None:
            # Same message as a wrong password — D-12 doesn't require
            # this, but there's no reason to let a login form confirm
            # which emails have staff accounts.
            error = "Incorrect email or password."
        elif is_locked_out(user, now):
            error = "This account is locked for 15 minutes after too many failed attempts. Contact the owner if you need immediate access."
        elif not verify_password(password, user.password_hash):
            register_failed_login(user, now)
            error = "Incorrect email or password."
        else:
            register_successful_login(user, now)
            sessions.log_in(request, user, now)
            next_url = _safe_next(request, request.POST.get("next") or request.GET.get("next"))
            if user.must_change_password:
                query = urlencode({"next": next_url})
                return redirect(f"{reverse('manage:change_password')}?{query}")
            return redirect(next_url)

    return render(request, "staff/login.html", {
        "form": form,
        "error": error,
        "next": request.GET.get("next", ""),
    })


def logout(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    sessions.log_out(request)
    return redirect("manage:login")


@staff_login_required
def change_password(request: HttpRequest) -> HttpResponse:
    # Scope note: `must_change_password` is enforced at the moment of
    # login (above — the post-login redirect goes here, not to `next`)
    # and nowhere else. A user who navigates away from this page before
    # submitting it can still reach other `/manage` pages on that
    # session; D-12's own wording ("forces a change on next login") is
    # about the login transition, not a persistent site-wide gate, and a
    # second enforcement point here would need care to avoid a redirect
    # loop against this same decorator. Revisit if the owner wants it
    # stricter — three staff accounts makes this a low-severity gap for
    # now, not an oversight.
    user = request.staff_user
    next_url = _safe_next(request, request.POST.get("next") or request.GET.get("next"))
    form = ChangePasswordForm(request.POST) if request.method == "POST" else ChangePasswordForm()

    if request.method == "POST" and form.is_valid():
        if not verify_password(form.cleaned_data["current_password"], user.password_hash):
            form.add_error("current_password", "That's not your current password.")
        else:
            user.password_hash = hash_password(form.cleaned_data["new_password"])
            user.must_change_password = False
            user.save(update_fields=["password_hash", "must_change_password"])
            messages.success(request, "Password changed.")
            return redirect(next_url)

    return render(request, "staff/change_password.html", {
        "form": form,
        "next": next_url,
        # Distinguishes "you must do this before continuing" (post owner
        # temp-password reset, D-12) from a voluntary change — same view,
        # different framing in the template.
        "forced": user.must_change_password,
    })


# ---------------------------------------------------------------- settings (owner-only)


def _settings_snapshot(instance: Settings) -> dict:
    """JSON-safe `{field: value}` for `SettingsEvent.diff` (D-24: "Settings
    is a single typed row with an events table") — same exclude set as
    `SettingsForm.Meta.exclude`.
    """
    data = model_to_dict(instance, exclude=["id", "updated_by", "updated_at"])
    return {key: _json_safe(value) for key, value in data.items()}


def _json_safe(value: object) -> object:
    if isinstance(value, (dt.date, dt.time, dt.datetime)):
        return value.isoformat()
    return value


def _diff_settings(before: dict, after: dict) -> dict:
    keys = set(before) | set(after)
    return {
        key: {"old": before.get(key), "new": after.get(key)}
        for key in keys
        if before.get(key) != after.get(key)
    }


@owner_required
def settings_view(request: HttpRequest) -> HttpResponse:
    instance = Settings.objects.filter(pk=1).first()
    creating = instance is None
    if creating:
        instance = Settings(id=1)
    before = {} if creating else _settings_snapshot(instance)

    if request.method == "POST":
        form = SettingsForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.id = 1
            obj.updated_by = request.staff_user
            obj.save()
            diff = _diff_settings(before, _settings_snapshot(obj))
            if diff:
                SettingsEvent.objects.create(user=request.staff_user, diff=diff)
            messages.success(request, "Settings saved.")
            return redirect("manage:settings")
    else:
        form = SettingsForm(instance=instance)

    return render(request, "staff/settings.html", {"form": form, "creating": creating})


# ---------------------------------------------------------------- kitchen desk (§12.4)


# §9.3's own table: exactly these four statuses ever appear on the
# kitchen board — never awaiting_eft/payment_review/cash_request (not
# confirmed yet), payment_expired/cancelled (dead), collected (done).
KITCHEN_BOARD_STATUSES = [
    OrderStatus.CONFIRMED_PREP, OrderStatus.CASH_DUE, OrderStatus.IN_KITCHEN, OrderStatus.READY,
]
# §9.3: ready is the collection board's primary status; in_kitchen shows
# "greyed, not ready"; collected shows "today, collapsed".
COLLECTION_BOARD_STATUSES = [OrderStatus.READY, OrderStatus.IN_KITCHEN, OrderStatus.COLLECTED]


def _parse_date_param(request: HttpRequest) -> dt.date:
    raw = request.GET.get("date")
    if raw:
        try:
            return dt.date.fromisoformat(raw)
        except ValueError:
            pass
    return now_sast().date()


def _date_label(date: dt.date) -> str:
    is_today = date == now_sast().date()
    prefix = "Today, " if is_today else ""
    return f"{prefix}{_DAY_NAMES_FULL[date.weekday()]} {date.day} {_MONTH_NAMES[date.month - 1]}"


@staff_login_required
def kitchen(request: HttpRequest) -> HttpResponse:
    """§12.4: date selector (default today), the summary view (grouped
    `dish_name_snapshot → option_key → SUM(quantity)`), the exceptions
    band (a note, a `kitchen_note`, or an allergen-flagged dish), the
    "Added after lock" band (derived from `confirmed_at` vs
    `kitchen_locked_at`, not a stored flag — correct regardless of which
    transition, `verify_eft` or `accept_cash`, put an order on the
    board), and the per-order ticket list `static/js/kitchen.js` drives
    `start_kitchen`/`mark_ready` from.
    """
    settings = Settings.current()
    date = _parse_date_param(request)
    trading_day = TradingDay.objects.filter(pk=date).first()
    context: dict[str, object] = {
        "date": date, "date_label": _date_label(date), "trading_day": trading_day,
        "prev_date": (date - dt.timedelta(days=1)).isoformat(),
        "next_date": (date + dt.timedelta(days=1)).isoformat(),
    }
    if trading_day is None:
        return render(request, "staff/kitchen.html", context)

    board_orders = list(
        Order.objects.filter(trading_day=trading_day, status__in=KITCHEN_BOARD_STATUSES)
        .select_related("payment")
        .prefetch_related("lines__dish")
        .order_by("slot__start_at", "order_number")
    )

    summary_map: dict[tuple[str, str], dict] = {}
    exceptions = []
    for order in board_orders:
        order_lines = list(order.lines.all())
        for line in order_lines:
            key = (line.dish_name_snapshot, line.option_key)
            entry = summary_map.setdefault(key, {
                "dish": line.dish_name_snapshot, "option_key": line.option_key,
                "qty": 0, "orders": [],
            })
            entry["qty"] += line.quantity
            entry["orders"].append(f"{order.order_number} ({line.quantity})")

        kitchen_notes = [line for line in order_lines if line.kitchen_note]
        allergen_lines = [line for line in order_lines if line.dish_id and line.dish.allergen_text]
        if order.note or kitchen_notes or allergen_lines:
            exceptions.append({
                "order": order, "note": order.note,
                "kitchen_notes": kitchen_notes, "allergen_lines": allergen_lines,
            })

    summary = sorted(summary_map.values(), key=lambda e: (e["dish"], e["option_key"]))

    added_after_lock = []
    if trading_day.kitchen_locked_at is not None:
        added_after_lock = [
            o for o in board_orders
            if o.confirmed_at is not None and o.confirmed_at > trading_day.kitchen_locked_at
        ]

    tickets = [
        {
            "order": order,
            "items_summary": ", ".join(
                f"{line.quantity}× {line.dish_name_snapshot}" for line in order.lines.all()
            ),
        }
        for order in board_orders
    ]

    occupying_today = Order.objects.filter(
        trading_day=trading_day, status__in=OCCUPYING_STATUSES,
    ).count()
    cash_occupying_today = Order.objects.filter(
        trading_day=trading_day, payment_method=PaymentMethod.CASH, status__in=OCCUPYING_STATUSES,
    ).count()

    context.update({
        "service_window": (
            f"{coerce_time(trading_day.window_start).strftime('%H:%M')}"
            f"–{coerce_time(trading_day.window_end).strftime('%H:%M')}"
        ),
        "summary": summary,
        "exceptions": exceptions,
        "added_after_lock": added_after_lock,
        "tickets": tickets,
        "meter_orders": {"value": occupying_today, "of": trading_day.daily_order_cap},
        "meter_cash": {"value": cash_occupying_today, "of": settings.cash_daily_cap},
    })
    return render(request, "staff/kitchen.html", context)


# ---------------------------------------------------------------- collection board (§12.5)


@staff_login_required
def collection_board(request: HttpRequest) -> HttpResponse:
    """§12.5: grouped by slot in time order, current slot highlighted;
    `ready` past `window_end + collection_grace_minutes` moves to its
    own "Uncollected" bucket instead of a slot group, with the
    "Close out day" action (`core.transitions.close_out_day`) shown once
    that deadline has passed.
    """
    settings = Settings.current()
    date = _parse_date_param(request)
    trading_day = TradingDay.objects.filter(pk=date).first()
    context: dict[str, object] = {
        "date": date, "date_label": _date_label(date), "trading_day": trading_day,
        "prev_date": (date - dt.timedelta(days=1)).isoformat(),
        "next_date": (date + dt.timedelta(days=1)).isoformat(),
    }
    if trading_day is None:
        return render(request, "staff/collection.html", context)

    now = now_sast()
    deadline = dt.datetime.combine(
        trading_day.date, trading_day.window_end, tzinfo=SAST,
    ) + dt.timedelta(minutes=settings.collection_grace_minutes)
    past_deadline = now >= deadline

    orders = (
        Order.objects.filter(trading_day=trading_day, status__in=COLLECTION_BOARD_STATUSES)
        .select_related("payment", "slot")
        .order_by("slot__start_at", "order_number")
    )

    current_slot = trading_day.slots.filter(start_at__lte=now.time(), end_at__gt=now.time()).first()

    groups: dict[int, dict] = {}
    uncollected = []
    for order in orders:
        if past_deadline and order.status == OrderStatus.READY:
            uncollected.append(order)
            continue
        group = groups.setdefault(order.slot_id, {"slot": order.slot, "orders": []})
        group["orders"].append(order)
    slots = sorted(groups.values(), key=lambda g: g["slot"].start_at)

    context.update({
        "slots": slots,
        "uncollected": uncollected,
        "current_slot_id": current_slot.pk if current_slot else None,
        "past_deadline": past_deadline,
        "closed_out": trading_day.closed_out_at is not None,
    })
    return render(request, "staff/collection.html", context)


# ---------------------------------------------------------------- EFT payment queue (§12.3)


@staff_login_required
def payments_queue(request: HttpRequest) -> HttpResponse:
    """§9.3's EFT queue board: exactly `awaiting_eft`/`payment_review`,
    hold expiry ascending (lapsed first), then slot start. Row actions
    (Verify/Reject/Extend hold/Expire now) POST to `manage:api_transition`
    (`staff/api.py`) via `static/js/payments.js` — this view only reads.
    """
    now = now_sast()
    orders = (
        Order.objects.filter(status__in=[OrderStatus.AWAITING_EFT, OrderStatus.PAYMENT_REVIEW])
        .select_related("payment", "slot", "trading_day")
        .order_by("hold_expires_at", "slot__start_at")
    )
    rows = []
    for order in orders:
        lapsed = order.hold_expires_at is not None and order.hold_expires_at < now
        remaining_seconds = (
            None if order.hold_expires_at is None
            else int((order.hold_expires_at - now).total_seconds())
        )
        rows.append({
            "order": order,
            "lapsed": lapsed,
            "remaining_seconds": remaining_seconds,
            "has_proof": order.payment.current_proof_media_id is not None,
        })
    return render(request, "staff/payments.html", {
        "rows": rows,
        "now_label": now.strftime("%H:%M"),
    })


# ---------------------------------------------------------------- cash requests (§12.2/M7)


@staff_login_required
def cash_requests(request: HttpRequest) -> HttpResponse:
    """The one piece of §12.2's Inbox this milestone needs on its own
    (spec's own board split names it there; "Inbox" itself, with the
    hold-lapsed/notes/recently-expired sections around it, is milestone
    9's board — see `core/transitions.py`'s module docstring). Exactly
    `cash_request` orders, oldest first — no date filter, since cash is
    same-day by default and this queue needs a same-day answer either
    way. Accept/Reject POST to `manage:api_transition` like every other
    board.
    """
    orders = (
        Order.objects.filter(status=OrderStatus.CASH_REQUEST)
        .select_related("slot", "trading_day")
        .order_by("created_at")
    )
    return render(request, "staff/cash_requests.html", {
        "orders": orders,
        "now_label": now_sast().strftime("%H:%M"),
    })


# ---------------------------------------------------------------- daily controls (§12.8)


@staff_login_required
def daily_controls_today(request: HttpRequest) -> HttpResponse:
    return redirect("manage:daily_controls", date=now_sast().date().isoformat())


@staff_login_required
def daily_controls(request: HttpRequest, date: str) -> HttpResponse:
    """§12.8: open/close the day, override window/cut-off/daily cap,
    per-slot capacity/close, per-dish available/`max_units`, internal
    notes — real ceilings on the same day (§20's own acceptance line:
    "sell out one dish and close one slot without editing the monthly
    menu"). Slot capacity can never go below current occupancy (a hard
    validation error, not a warning). Closing the day, or a slot that
    still has occupying orders, needs typed confirmation (a checkbox
    that only appears once there's something to confirm) and lists the
    affected orders, each closing slot offering a "Move all to…" picker
    (`static/js/daily_controls.js` -> `manage:api_move_all_orders`,
    `core.transitions`' already-tested `change_slot`).
    """
    try:
        target_date = dt.date.fromisoformat(date)
    except ValueError:
        raise Http404("Invalid date.") from None

    settings = Settings.current()
    trading_day = materialise_day(target_date, settings)
    form = TradingDayForm(instance=trading_day)

    slots = list(trading_day.slots.order_by("start_at"))
    slot_occupancy = {
        s.pk: Order.objects.filter(slot=s, status__in=OCCUPYING_STATUSES).count() for s in slots
    }
    dishes = active_dishes()
    avail_by_dish = {a.dish_id: a for a in trading_day.dish_availability.all()}
    used_units = dish_units_used(trading_day, [d.pk for d in dishes]) if dishes else {}

    errors: list[str] = []
    confirm_needed = False
    closing_slots: list[Slot] = []
    affected_orders: dict[int, Order] = {}

    if request.method == "POST":
        form = TradingDayForm(request.POST, instance=trading_day)
        slot_updates = []
        for s in slots:
            try:
                new_capacity = int(request.POST.get(f"slot_capacity_{s.pk}", ""))
            except ValueError:
                errors.append(f"Slot {s.start_at:%H:%M}: enter a valid capacity.")
                continue
            occupying = slot_occupancy[s.pk]
            if new_capacity < occupying:
                errors.append(
                    f"Slot {s.start_at:%H:%M}: capacity can't go below {occupying}, "
                    "its current occupancy.",
                )
                continue
            closed = f"slot_closed_{s.pk}" in request.POST
            slot_updates.append((s, new_capacity, closed))
            if closed and not s.is_closed and occupying > 0:
                confirm_needed = True
                closing_slots.append(s)
                for order in Order.objects.filter(slot=s, status__in=OCCUPYING_STATUSES):
                    affected_orders[order.pk] = order

        dish_updates = []
        for d in dishes:
            available = f"dish_available_{d.pk}" in request.POST
            raw = request.POST.get(f"dish_max_units_{d.pk}", "").strip()
            max_units = None
            if raw:
                try:
                    max_units = int(raw)
                    if max_units < 0:
                        raise ValueError
                except ValueError:
                    errors.append(f"{d.name}: enter a whole number of units, or leave it blank.")
                    continue
            dish_updates.append((d, available, max_units))

        day_will_be_open = "is_open" in request.POST
        if trading_day.is_open and not day_will_be_open:
            day_orders = Order.objects.filter(
                trading_day=trading_day, status__in=OCCUPYING_STATUSES,
            )
            for order in day_orders:
                affected_orders[order.pk] = order
            if affected_orders:
                confirm_needed = True

        if not form.is_valid():
            errors.extend(
                f"{field}: {err}" for field, errs in form.errors.items() for err in errs
            )

        confirmed = request.POST.get("confirm_close") == "1"
        if not errors and (not confirm_needed or confirmed):
            with transaction.atomic():
                form.save()
                for s, new_capacity, closed in slot_updates:
                    s.capacity = new_capacity
                    s.is_closed = closed
                    s.save(update_fields=["capacity", "is_closed"])
                for d, available, max_units in dish_updates:
                    DayDishAvailability.objects.update_or_create(
                        trading_day=trading_day, dish=d,
                        defaults={"is_available": available, "max_units": max_units},
                    )
            messages.success(request, "Daily controls saved.")
            return redirect("manage:daily_controls", date=target_date.isoformat())
        if not errors and confirm_needed and not confirmed:
            messages.error(request, "Confirm the affected orders below, or move them first.")

    slot_rows = [
        {
            "slot": s,
            "occupying": slot_occupancy[s.pk],
            "capacity": request.POST.get(f"slot_capacity_{s.pk}", s.capacity),
            "closed": (
                f"slot_closed_{s.pk}" in request.POST if request.method == "POST" else s.is_closed
            ),
        }
        for s in slots
    ]
    dish_rows = [
        {
            "dish": d,
            "used_units": used_units.get(d.pk, 0),
            "available": (
                f"dish_available_{d.pk}" in request.POST if request.method == "POST"
                else avail_by_dish[d.pk].is_available if d.pk in avail_by_dish else True
            ),
            "max_units": (
                request.POST.get(f"dish_max_units_{d.pk}", "") if request.method == "POST"
                else (avail_by_dish[d.pk].max_units if d.pk in avail_by_dish else None)
            ),
        }
        for d in dishes
    ]

    return render(request, "staff/daily_controls.html", {
        "date": target_date,
        "date_label": _date_label(target_date),
        "trading_day": trading_day,
        "form": form,
        "slot_rows": slot_rows,
        "dish_rows": dish_rows,
        "errors": errors,
        "confirm_needed": confirm_needed,
        "closing_slots": closing_slots,
        "affected_orders": list(affected_orders.values()),
        "other_open_slots": [s for s in slots if not s.is_closed],
        "prev_date": (target_date - dt.timedelta(days=1)).isoformat(),
        "next_date": (target_date + dt.timedelta(days=1)).isoformat(),
    })


# ---------------------------------------------------------------- menu editor (§12.7, M8 remainder)


def _dishes_with_occupying_orders(dish_ids: list[int]) -> dict[int, int]:
    """`{dish_id: count of occupying orders referencing it}` — an
    "occupying" order is one of `OCCUPYING_STATUSES` (not yet expired/
    cancelled/collected). Archiving is allowed regardless (D-25: order
    lines snapshot their own name/price independently of `Dish`), but the
    editor must show this count before the confirm gate lets it through.
    """
    if not dish_ids:
        return {}
    # distinct order count per dish, not line count — a dish can appear on
    # the same order twice (two option combinations).
    counts: dict[int, int] = {}
    for dish_id in dish_ids:
        counts[dish_id] = (
            Order.objects.filter(status__in=OCCUPYING_STATUSES, lines__dish_id=dish_id)
            .distinct()
            .count()
        )
    return counts


@staff_login_required
def menu_list(request: HttpRequest) -> HttpResponse:
    """§12.7's dish list: every dish including archived ones, in the
    same category/sort_order/name ordering the public menu uses (plus
    archived ones trailing after, grouped by category) — manager+ access
    (both roles the site has are manager+; nothing above manager exists
    per §4's role table), same as daily controls.
    """
    dishes = list(Dish.objects.all().order_by("category", "sort_order", "name"))
    dish_ids = [d.pk for d in dishes]
    occupying = _dishes_with_occupying_orders(dish_ids)
    rows = [
        {
            "dish": d,
            "occupying_orders": occupying.get(d.pk, 0),
            "price_rand": f"{d.price_cents / 100:.2f}",
        }
        for d in dishes
    ]
    return render(request, "staff/menu_list.html", {"rows": rows})


@staff_login_required
def dish_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = DishForm(request.POST)
        if form.is_valid():
            dish = form.save()
            messages.success(request, f"{dish.name} created.")
            return redirect("manage:dish_edit", dish_id=dish.pk)
    else:
        form = DishForm()
    return render(request, "staff/dish_form.html", {
        "form": form, "dish": None, "editing": False,
    })


def _handle_image_upload(request: HttpRequest, dish: Dish) -> None:
    upload = request.FILES.get("image")
    if not upload:
        return
    data = upload.read()
    try:
        mime_type = validate_dish_image(data)
    except InvalidUpload as exc:
        messages.error(request, str(exc))
        return
    storage_key = store_dish_image_bytes(data, mime_type)
    media = Media.objects.create(
        kind=MediaKind.DISH_IMAGE,
        storage_key=storage_key,
        mime_type=mime_type,
        byte_size=len(data),
        sha256=sha256_digest(data),
        dish=dish,
        uploaded_by=request.staff_user,
    )
    dish.image_media = media
    dish.save(update_fields=["image_media"])
    messages.success(request, "Image uploaded.")


@staff_login_required
def dish_edit(request: HttpRequest, dish_id: int) -> HttpResponse:
    """Edit an existing dish (slug immutable — `DishForm(editing=True)`
    drops the field from the form entirely), handle the image upload,
    and manage this dish's options/values inline via raw POST-key
    parsing, the same pattern `daily_controls` uses for its per-slot/
    per-dish rows (no formset — a variable number of options/values).
    """
    dish = Dish.objects.filter(pk=dish_id).first()
    if dish is None:
        raise Http404("Dish not found.")

    if request.method == "POST":
        action = request.POST.get("action", "save")

        if action == "upload_image":
            _handle_image_upload(request, dish)
            return redirect("manage:dish_edit", dish_id=dish.pk)

        if action == "add_option":
            option_form = DishOptionForm(request.POST)
            if option_form.is_valid():
                option = option_form.save(commit=False)
                option.dish = dish
                option.save()
                messages.success(request, f"Option '{option.name}' added.")
            else:
                messages.error(
                    request,
                    "; ".join(
                        f"{f}: {e}" for f, errs in option_form.errors.items() for e in errs
                    ),
                )
            return redirect("manage:dish_edit", dish_id=dish.pk)

        if action == "delete_option":
            option_id = request.POST.get("option_id")
            DishOption.objects.filter(pk=option_id, dish=dish).delete()
            messages.success(request, "Option removed.")
            return redirect("manage:dish_edit", dish_id=dish.pk)

        if action == "add_value":
            option = DishOption.objects.filter(
                pk=request.POST.get("option_id"), dish=dish,
            ).first()
            if option is None:
                raise Http404("Option not found.")
            value_form = DishOptionValueForm(request.POST)
            if value_form.is_valid():
                value = value_form.save(commit=False)
                value.option = option
                # The inline "add value" form (dish_form.html) has no
                # availability checkbox — a plain unchecked BooleanField
                # would otherwise silently override the model's own
                # `is_available=True` default with False.
                if "is_available" not in request.POST:
                    value.is_available = True
                value.save()
                messages.success(request, f"Value '{value.name}' added.")
            else:
                messages.error(
                    request,
                    "; ".join(
                        f"{f}: {e}" for f, errs in value_form.errors.items() for e in errs
                    ),
                )
            return redirect("manage:dish_edit", dish_id=dish.pk)

        if action == "delete_value":
            value_id = request.POST.get("value_id")
            DishOptionValue.objects.filter(pk=value_id, option__dish=dish).delete()
            messages.success(request, "Value removed.")
            return redirect("manage:dish_edit", dish_id=dish.pk)

        if action == "toggle_value_available":
            value = DishOptionValue.objects.filter(
                pk=request.POST.get("value_id"), option__dish=dish,
            ).first()
            if value is not None:
                value.is_available = not value.is_available
                value.save(update_fields=["is_available"])
            return redirect("manage:dish_edit", dish_id=dish.pk)

        # Plain dish-field save.
        form = DishForm(request.POST, instance=dish, editing=True)
        if form.is_valid():
            form.save()
            messages.success(request, f"{dish.name} saved.")
            return redirect("manage:dish_edit", dish_id=dish.pk)
    else:
        form = DishForm(instance=dish, editing=True)

    options = list(
        dish.options.order_by("sort_order", "name").prefetch_related("values")
    )
    occupying_orders = _dishes_with_occupying_orders([dish.pk]).get(dish.pk, 0)

    return render(request, "staff/dish_form.html", {
        "form": form,
        "dish": dish,
        "editing": True,
        "options": options,
        "option_form": DishOptionForm(),
        "value_form": DishOptionValueForm(),
        "occupying_orders": occupying_orders,
        "archived": dish.archived_at is not None,
    })


@staff_login_required
def dish_archive(request: HttpRequest, dish_id: int) -> HttpResponse:
    """§12.7/D-25: soft delete only. Archiving a dish that still has
    occupying orders is allowed (their `order_lines` rows carry their
    own name/price snapshot, independent of this `Dish` row), but — same
    confirm-gate UX as `daily_controls` closing a slot/day with
    occupying orders — the staff member must see the affected-order
    count and type/tick a confirmation before it goes through.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    dish = Dish.objects.filter(pk=dish_id).first()
    if dish is None:
        raise Http404("Dish not found.")

    occupying_orders = _dishes_with_occupying_orders([dish.pk]).get(dish.pk, 0)
    confirmed = request.POST.get("confirm_archive") == "1"
    if occupying_orders and not confirmed:
        messages.error(
            request,
            f"{dish.name} has {occupying_orders} occupying order(s). "
            "Confirm to archive it anyway — those orders keep their own snapshot.",
        )
        return redirect("manage:dish_edit", dish_id=dish.pk)

    dish.archived_at = now_sast()
    dish.is_active_on_menu = False
    dish.save(update_fields=["archived_at", "is_active_on_menu"])
    messages.success(request, f"{dish.name} archived.")
    return redirect("manage:menu_list")


@staff_login_required
def dish_unarchive(request: HttpRequest, dish_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    dish = Dish.objects.filter(pk=dish_id).first()
    if dish is None:
        raise Http404("Dish not found.")
    dish.archived_at = None
    dish.save(update_fields=["archived_at"])
    messages.success(request, f"{dish.name} unarchived.")
    return redirect("manage:dish_edit", dish_id=dish.pk)


# ---------------------------------------------------------------- assisted order entry (§12.9, M9)


def _slot_rows_for_day(trading_day: TradingDay) -> list[dict]:
    slots = list(trading_day.slots.order_by("start_at"))
    rows = []
    for s in slots:
        occupying = Order.objects.filter(slot=s, status__in=OCCUPYING_STATUSES).count()
        rows.append({
            "slot": s, "occupying": occupying, "full": s.is_closed or occupying >= s.capacity,
        })
    return rows


@staff_login_required
def assisted_order_new(request: HttpRequest) -> HttpResponse:
    """§12.9's assisted order entry: same field validation and the same
    §8.3 transaction (`core.capacity.reserve()`) as the public checkout
    API — this view is a staff-facing form over the exact same
    `ReservationRequest`/`reserve()` call `public/api.py::checkout`
    makes, so capacity parity with web checkout is structural, not just
    tested-for. Staff pick quantities/options directly against every
    active dish for the chosen day (no client-side cart — a raw-POST-key
    row per dish, same pattern `daily_controls`/`dish_form` already use
    for a variable number of rows) rather than the customer-facing
    `/order/` + `/checkout/` pair.

    EFT orders default to a plain hold (`awaiting_eft`, same as web
    checkout); `eft_mode` escalates it in the same request — "payment_review"
    (customer says they've paid, no proof needed yet — `mark_payment_review`)
    or "confirmed_prep" (staff already saw the funds — `verify_eft`,
    D-18's mandatory reason). Cash assisted orders land in `cash_request`
    exactly like a web cash order (M7's cash queue picks it up from there
    — no special-cased assisted acceleration).
    """
    settings = Settings.current()
    today = now_sast().date()

    date_param = (
        request.POST.get("date") if request.method == "POST" else request.GET.get("date")
    ) or today.isoformat()
    try:
        selected_date = dt.date.fromisoformat(date_param)
    except ValueError:
        selected_date = today
    if not (today <= selected_date <= today + dt.timedelta(days=settings.preorder_days)):
        selected_date = today
    trading_day = materialise_days(selected_date, settings, count=1)[0]

    menu_dishes = dishes_for_date(trading_day, with_options=True)
    slot_rows = _slot_rows_for_day(trading_day)
    is_today = selected_date == today

    errors: list[str] = []
    form_values: dict[str, str] = {}

    if request.method == "POST" and request.POST.get("action") == "place_order":
        form_values = {
            "customer_name": request.POST.get("customer_name", ""),
            "customer_mobile": request.POST.get("customer_mobile", ""),
            "note": request.POST.get("note", ""),
            "source": request.POST.get("source", ""),
            "payment_method": request.POST.get("payment_method", ""),
            "after_cutoff_reason": request.POST.get("after_cutoff_reason", ""),
        }
        customer_name = form_values["customer_name"].strip()
        mobile_raw = form_values["customer_mobile"].strip()
        note = form_values["note"].strip()
        source = form_values["source"]
        payment_method = form_values["payment_method"]
        slot_id_raw = request.POST.get("slot_id", "")
        after_cutoff_reason = form_values["after_cutoff_reason"].strip()
        eft_mode = request.POST.get("eft_mode", "hold")
        eft_confirm_reason = request.POST.get("eft_confirm_reason", "").strip()

        if not (2 <= len(customer_name) <= 80):
            errors.append("Customer name must be 2-80 characters.")

        customer_mobile = ""
        try:
            customer_mobile = normalize_sa_mobile(mobile_raw)
        except InvalidPhoneNumber:
            errors.append("Enter a valid South African mobile number.")

        if source not in ASSISTED_SOURCES:
            errors.append("Choose an order source.")

        if payment_method not in (PaymentMethod.EFT, PaymentMethod.CASH):
            errors.append("Choose a payment method.")

        if not slot_id_raw.isdigit():
            errors.append("Choose a collection slot.")

        lines: list[CheckoutLine] = []
        for md in menu_dishes:
            qty_raw = request.POST.get(f"qty_{md.id}", "").strip()
            if not qty_raw:
                continue
            try:
                qty = int(qty_raw)
            except ValueError:
                errors.append(f"{md.name}: enter a whole number.")
                continue
            if qty <= 0:
                continue
            option_value_ids: list[int] = []
            for option in md.options:
                if option.required:
                    val = request.POST.get(f"opt_{md.id}_{option.id}")
                    if val and val.isdigit():
                        option_value_ids.append(int(val))
                else:
                    for value in option.values:
                        if request.POST.get(f"opt_{md.id}_{option.id}_{value.id}"):
                            option_value_ids.append(value.id)
            lines.append(
                CheckoutLine(dish_id=md.id, quantity=qty, option_value_ids=option_value_ids)
            )

        if not lines:
            errors.append("Add at least one dish.")

        if eft_mode == "confirmed_prep" and not eft_confirm_reason:
            errors.append("A reason is required to confirm payment was already seen (D-18).")

        if not errors:
            req = ReservationRequest(
                trading_day_date=selected_date,
                slot_id=int(slot_id_raw),
                payment_method=payment_method,
                customer_name=customer_name,
                customer_mobile_e164=customer_mobile,
                lines=lines,
                note=note,
                source=source,
                created_by_user=request.staff_user,
                is_staff_assisted=True,
                after_cutoff_reason=after_cutoff_reason or None,
            )
            try:
                order = reserve(req, settings)
            except CapacityError as exc:
                errors.append(exc.message)
            else:
                if payment_method == PaymentMethod.EFT and eft_mode != "hold":
                    actor = Actor(kind=ActorKind.STAFF, user=request.staff_user)
                    try:
                        if eft_mode == "payment_review":
                            apply_transition(
                                order, "mark_payment_review", actor, OrderStatus.AWAITING_EFT,
                            )
                        elif eft_mode == "confirmed_prep":
                            apply_transition(
                                order, "verify_eft", actor, OrderStatus.AWAITING_EFT,
                                reason=eft_confirm_reason,
                            )
                    except TransitionError as exc:
                        messages.warning(
                            request,
                            f"Order {order.order_number} was created but couldn't be "
                            f"escalated: {exc.message}",
                        )
                        return redirect("manage:inbox")
                messages.success(request, f"Order {order.order_number} created.")
                return redirect("manage:inbox")

    return render(request, "staff/assisted_order_form.html", {
        "date": selected_date,
        "date_label": _date_label(selected_date),
        "prev_date": (selected_date - dt.timedelta(days=1)).isoformat(),
        "next_date": (selected_date + dt.timedelta(days=1)).isoformat(),
        "today_iso": today.isoformat(),
        "min_date": today.isoformat(),
        "max_date": (today + dt.timedelta(days=settings.preorder_days)).isoformat(),
        "menu_dishes": menu_dishes,
        "slot_rows": slot_rows,
        "is_today": is_today,
        "assisted_after_cutoff_enabled": settings.assisted_after_cutoff_enabled,
        "cash_enabled": settings.cash_enabled,
        "sources": [(v, lbl) for v, lbl in OrderSource.choices if v in ASSISTED_SOURCES],
        "errors": errors,
        "form_values": form_values,
    })


# ---------------------------------------------------------------- preorder calendar (§12.6, M9)


DISH_WARNING_THRESHOLD = 0.8  # §12.6: "dish warnings (>=80% of max_units)"


@staff_login_required
def calendar(request: HttpRequest) -> HttpResponse:
    """§12.6's 8-day grid (today + 7): open/closed, orders vs day cap,
    cash count vs cash cap, per-slot heat (occupancy/capacity), dish
    warnings at >=80% of `max_units`. Tap-through to
    `manage:daily_controls`.
    """
    settings = Settings.current()
    today = now_sast().date()
    trading_days = materialise_days(today, settings, count=8)

    days = []
    for td in trading_days:
        occupying = Order.objects.filter(trading_day=td, status__in=OCCUPYING_STATUSES).count()
        cash_occupying = Order.objects.filter(
            trading_day=td, payment_method=PaymentMethod.CASH, status__in=OCCUPYING_STATUSES,
        ).count()

        slots = list(td.slots.order_by("start_at"))
        slot_heat = []
        for s in slots:
            s_occupying = Order.objects.filter(slot=s, status__in=OCCUPYING_STATUSES).count()
            pct = round(100 * s_occupying / s.capacity) if s.capacity else 0
            slot_heat.append({"slot": s, "occupying": s_occupying, "pct": pct})

        avail_rows = list(
            td.dish_availability.select_related("dish").filter(max_units__isnull=False)
        )
        dish_ids = [a.dish_id for a in avail_rows]
        used = dish_units_used(td, dish_ids) if dish_ids else {}
        dish_warnings = [
            {"dish": a.dish, "used": used.get(a.dish_id, 0), "max_units": a.max_units}
            for a in avail_rows
            if a.max_units and used.get(a.dish_id, 0) / a.max_units >= DISH_WARNING_THRESHOLD
        ]

        days.append({
            "date": td.date,
            "date_label": _date_label(td.date),
            "trading_day": td,
            "orders": {"value": occupying, "of": td.daily_order_cap},
            "cash": {"value": cash_occupying, "of": settings.cash_daily_cap},
            "slot_heat": slot_heat,
            "dish_warnings": dish_warnings,
        })

    return render(request, "staff/calendar.html", {"days": days})


# ---------------------------------------------------------------- inbox (§12.2, M9)


_RECENT_ASSISTED_LIMIT = 20
_RECENTLY_EXPIRED_WINDOW = dt.timedelta(hours=48)


@staff_login_required
def inbox(request: HttpRequest) -> HttpResponse:
    """§12.2's staff landing page — sections in order: Cash requests
    (accept/reject inline, same `manage:api_transition` M7's own cash
    queue already uses), Hold-lapsed / SLA-breached reviews, Orders with
    notes, Recent assisted, Recently expired (with a reinstate action).
    Row actions: open (the order's own status page — no dedicated staff
    order-detail screen exists yet, and the public one already shows
    everything a customer sees, token-gated the same way it always is),
    assign (`manage:api_assign_order`), contact (`wa.me` link, rendered
    directly — no JS needed for a plain link), change slot (the existing
    `change_slot` transition via a per-row slot picker).
    """
    now = now_sast()
    settings = Settings.current()

    cash_orders = list(
        Order.objects.filter(status=OrderStatus.CASH_REQUEST)
        .select_related("slot", "trading_day")
        .order_by("created_at")
    )

    hold_lapsed = list(
        Order.objects.filter(status=OrderStatus.AWAITING_EFT, hold_expires_at__lt=now)
        .select_related("slot", "trading_day")
        .order_by("hold_expires_at")
    )

    sla_deadline = now - dt.timedelta(minutes=settings.payment_review_sla_minutes)
    sla_breached = list(
        Order.objects.filter(status=OrderStatus.PAYMENT_REVIEW)
        .filter(
            Q(payment__proof_uploaded_at__lt=sla_deadline)
            | (Q(payment__proof_uploaded_at__isnull=True) & Q(created_at__lt=sla_deadline))
        )
        .select_related("slot", "trading_day", "payment")
        .order_by("created_at")
    )

    notes = list(
        Order.objects.filter(status__in=OCCUPYING_STATUSES)
        .exclude(note__isnull=True).exclude(note="")
        .select_related("slot", "trading_day")
        .order_by("-created_at")[:30]
    )

    recent_assisted = list(
        Order.objects.filter(source__in=ASSISTED_SOURCES)
        .select_related("slot", "trading_day", "created_by_user")
        .order_by("-created_at")[:_RECENT_ASSISTED_LIMIT]
    )

    recently_expired = list(
        Order.objects.filter(
            status=OrderStatus.PAYMENT_EXPIRED, updated_at__gte=now - _RECENTLY_EXPIRED_WINDOW,
        )
        .select_related("slot", "trading_day")
        .order_by("-updated_at")
    )

    all_groups = (cash_orders, hold_lapsed, sla_breached, notes, recent_assisted, recently_expired)
    trading_day_ids = {o.trading_day_id for group in all_groups for o in group}
    slots_by_day: dict[int, list[Slot]] = {}
    if trading_day_ids:
        for s in Slot.objects.filter(
            trading_day_id__in=trading_day_ids, is_closed=False,
        ).order_by("start_at"):
            slots_by_day.setdefault(s.trading_day_id, []).append(s)

    return render(request, "staff/inbox.html", {
        "cash_orders": cash_orders,
        "hold_lapsed": hold_lapsed,
        "sla_breached": sla_breached,
        "notes": notes,
        "recent_assisted": recent_assisted,
        "recently_expired": recently_expired,
        "slots_by_day": slots_by_day,
        "now_label": now.strftime("%H:%M"),
        "support_whatsapp_e164": settings.support_whatsapp_e164,
    })
