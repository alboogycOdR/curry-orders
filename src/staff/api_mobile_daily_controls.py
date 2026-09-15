"""Staff mobile JSON for the Daily controls screen (Phase 6 —
docs/mobile/FLUTTER_APP_PLAN.md). One endpoint, `daily_controls_json`,
handling both `GET` (current state) and `POST` (save changes) on the
same URL — mirrors `staff/views.py::daily_controls` exactly (same
validation, same confirmation-before-closing-occupied-slots/day dance),
reshaped into JSON instead of a server-rendered form/template. Any
staff role — despite touching capacity/day-open, the web view is not
owner-gated either, so this isn't.

The "Move all to…" helper is NOT here: the app calls the existing
`POST /manage/api/days/<date>/slots/<slot_id>/move-all`
(`staff.api.move_all_orders`) directly, same as the web boards' own JS.
"""
from __future__ import annotations

import datetime as dt
import json

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from core.capacity import OCCUPYING_STATUSES, dish_units_used
from core.materialise import materialise_day
from core.menu import active_dishes
from core.models import DayDishAvailability, Dish, Order, Settings, Slot, TradingDay

from .api_mobile import _error_response, staff_login_required_json

# `confirmation_required` isn't one of `api_mobile._ERROR_STATUS`'s codes
# (only this screen needs it) — `_error_response`'s own default (422)
# already covers it, so this local dict exists only for readability/
# documentation, not because `_error_response` looks it up here too.
_CONFIRMATION_REQUIRED_STATUS = 422


# ---------------------------------------------------------------- read side


def _time_str(value: dt.time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def _day_json(trading_day: TradingDay) -> dict[str, object]:
    return {
        "is_open": trading_day.is_open,
        "daily_order_cap": trading_day.daily_order_cap,
        "cutoff_time": _time_str(trading_day.cutoff_time),
        "window_start": _time_str(trading_day.window_start),
        "window_end": _time_str(trading_day.window_end),
        "notes_internal": trading_day.notes_internal or "",
    }


def _slot_json(slot: Slot, occupying: int) -> dict[str, object]:
    return {
        "id": slot.pk,
        "label": f"{slot.start_at:%H:%M}–{slot.end_at:%H:%M}",
        "capacity": slot.capacity,
        # Current occupancy -- the client can never set `capacity` below
        # this (see `_apply_slot_updates` below).
        "min_capacity": occupying,
        "closed": slot.is_closed,
        "occupying_count": occupying,
    }


def _dish_json(dish: Dish, avail: DayDishAvailability | None, used: int) -> dict[str, object]:
    return {
        "id": dish.pk,
        "name": dish.name,
        "available": avail.is_available if avail is not None else True,
        "max_units": avail.max_units if avail is not None else None,
        "used_today": used,
    }


def _state_json(target_date: dt.date, trading_day: TradingDay) -> dict[str, object]:
    slots = list(trading_day.slots.order_by("start_at"))
    occupancy = {
        s.pk: Order.objects.filter(slot=s, status__in=OCCUPYING_STATUSES).count() for s in slots
    }
    dishes = active_dishes()
    avail_by_dish = {a.dish_id: a for a in trading_day.dish_availability.all()}
    used_units = dish_units_used(trading_day, [d.pk for d in dishes]) if dishes else {}

    return {
        "date": target_date.isoformat(),
        "day": _day_json(trading_day),
        "slots": [_slot_json(s, occupancy[s.pk]) for s in slots],
        "dishes": [
            _dish_json(d, avail_by_dish.get(d.pk), used_units.get(d.pk, 0)) for d in dishes
        ],
    }


# ---------------------------------------------------------------- write side


def _parse_time(raw: object) -> tuple[dt.time | None, str | None]:
    if not isinstance(raw, str) or not raw.strip():
        return None, "This field is required."
    text = raw.strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return dt.datetime.strptime(text, fmt).time(), None
        except ValueError:
            continue
    return None, "Enter a valid time (HH:MM)."


def _parse_day(
    day_data: dict[str, object], trading_day: TradingDay, errors: list[str], fields: dict[str, str]
) -> dict[str, object]:
    is_open = bool(day_data.get("is_open", trading_day.is_open))

    daily_order_cap = trading_day.daily_order_cap
    try:
        daily_order_cap = int(day_data.get("daily_order_cap", trading_day.daily_order_cap))
        if daily_order_cap < 0:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("Daily order cap: enter a whole number, 0 or more.")
        fields["day.daily_order_cap"] = "Enter a whole number, 0 or more."
        daily_order_cap = trading_day.daily_order_cap

    cutoff_time, err = _parse_time(day_data.get("cutoff_time"))
    if err:
        errors.append(f"Cut-off time: {err}")
        fields["day.cutoff_time"] = err
        cutoff_time = trading_day.cutoff_time

    window_start, err = _parse_time(day_data.get("window_start"))
    if err:
        errors.append(f"Window start: {err}")
        fields["day.window_start"] = err
        window_start = trading_day.window_start

    window_end, err = _parse_time(day_data.get("window_end"))
    if err:
        errors.append(f"Window end: {err}")
        fields["day.window_end"] = err
        window_end = trading_day.window_end

    if window_start is not None and window_end is not None and window_start >= window_end:
        errors.append("Window start must be before window end.")
        fields["day.window_end"] = "Must be after window start."
        window_start, window_end = trading_day.window_start, trading_day.window_end

    notes_raw = day_data.get("notes_internal")
    notes_internal = notes_raw.strip() if isinstance(notes_raw, str) else ""

    return {
        "is_open": is_open,
        "daily_order_cap": daily_order_cap,
        "cutoff_time": cutoff_time,
        "window_start": window_start,
        "window_end": window_end,
        "notes_internal": notes_internal or None,
    }


def _apply_slot_updates(
    slots_data: list[object],
    slots: list[Slot],
    occupancy: dict[int, int],
    errors: list[str],
    fields: dict[str, str],
) -> tuple[list[tuple[Slot, int, bool]], dict[int, Order]]:
    """Mirrors `views.py::daily_controls`'s per-slot loop: capacity can
    never drop below current occupancy, and any slot newly closed while
    it still has occupying orders needs confirmation (collected into
    `affected_orders`, keyed by order id the same way the web view's
    `dict[int, Order]` de-dupes an order appearing under more than one
    closing slot).
    """
    by_id = {s.pk: s for s in slots}
    input_by_id: dict[int, dict[str, object]] = {}
    for raw in slots_data:
        if isinstance(raw, dict) and isinstance(raw.get("id"), int) and raw["id"] in by_id:
            input_by_id[raw["id"]] = raw

    updates: list[tuple[Slot, int, bool]] = []
    affected_orders: dict[int, Order] = {}

    for slot in slots:
        raw = input_by_id.get(slot.pk)
        if raw is None:
            # Not submitted -- leave this slot exactly as it is.
            updates.append((slot, slot.capacity, slot.is_closed))
            continue

        occupying = occupancy[slot.pk]
        try:
            new_capacity = int(raw.get("capacity"))
        except (TypeError, ValueError):
            errors.append(f"Slot {slot.start_at:%H:%M}: enter a valid capacity.")
            fields[f"slot.{slot.pk}.capacity"] = "Enter a whole number."
            continue
        if new_capacity < 0:
            errors.append(f"Slot {slot.start_at:%H:%M}: capacity can't be negative.")
            fields[f"slot.{slot.pk}.capacity"] = "Can't be negative."
            continue
        if new_capacity < occupying:
            errors.append(
                f"Slot {slot.start_at:%H:%M}: capacity can't go below {occupying}, "
                "its current occupancy."
            )
            fields[f"slot.{slot.pk}.capacity"] = f"Can't go below {occupying} (current occupancy)."
            continue

        closed = bool(raw.get("closed"))
        updates.append((slot, new_capacity, closed))
        if closed and not slot.is_closed and occupying > 0:
            for order in Order.objects.filter(slot=slot, status__in=OCCUPYING_STATUSES):
                affected_orders[order.pk] = order

    return updates, affected_orders


def _apply_dish_updates(
    dishes_data: list[object],
    dishes: list[Dish],
    avail_by_dish: dict[int, DayDishAvailability],
    errors: list[str],
    fields: dict[str, str],
) -> list[tuple[Dish, bool, int | None]]:
    by_id = {d.pk: d for d in dishes}
    input_by_id: dict[int, dict[str, object]] = {}
    for raw in dishes_data:
        if isinstance(raw, dict) and isinstance(raw.get("id"), int) and raw["id"] in by_id:
            input_by_id[raw["id"]] = raw

    updates: list[tuple[Dish, bool, int | None]] = []
    for dish in dishes:
        raw = input_by_id.get(dish.pk)
        current = avail_by_dish.get(dish.pk)
        if raw is None:
            available = current.is_available if current is not None else True
            max_units = current.max_units if current is not None else None
            updates.append((dish, available, max_units))
            continue

        available = bool(raw.get("available", True))
        raw_max = raw.get("max_units")
        max_units: int | None = None
        if raw_max is not None and raw_max != "":
            try:
                max_units = int(raw_max)
                if max_units < 0:
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"{dish.name}: enter a whole number of units, or leave it blank.")
                fields[f"dish.{dish.pk}.max_units"] = "Enter a whole number, or leave blank."
                continue
        updates.append((dish, available, max_units))

    return updates


def _post(request: HttpRequest, target_date: dt.date, trading_day: TradingDay) -> JsonResponse:
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _error_response("validation_error", "Malformed JSON body.")
    if not isinstance(data, dict):
        return _error_response("validation_error", "Malformed JSON body.")

    day_data = data.get("day") if isinstance(data.get("day"), dict) else {}
    slots_data = data.get("slots") if isinstance(data.get("slots"), list) else []
    dishes_data = data.get("dishes") if isinstance(data.get("dishes"), list) else []
    confirm = data.get("confirm_affecting_orders") is True

    errors: list[str] = []
    fields: dict[str, str] = {}

    day_values = _parse_day(day_data, trading_day, errors, fields)

    slots = list(trading_day.slots.order_by("start_at"))
    occupancy = {
        s.pk: Order.objects.filter(slot=s, status__in=OCCUPYING_STATUSES).count() for s in slots
    }
    slot_updates, affected_orders = _apply_slot_updates(
        slots_data, slots, occupancy, errors, fields,
    )

    dishes = active_dishes()
    avail_by_dish = {a.dish_id: a for a in trading_day.dish_availability.all()}
    dish_updates = _apply_dish_updates(dishes_data, dishes, avail_by_dish, errors, fields)

    if trading_day.is_open and not day_values["is_open"]:
        for order in Order.objects.filter(
            trading_day=trading_day, status__in=OCCUPYING_STATUSES,
        ):
            affected_orders[order.pk] = order

    if errors:
        return _error_response("validation_error", " ".join(errors), fields=fields)

    if affected_orders and not confirm:
        return _error_response(
            "confirmation_required",
            "These orders will be affected.",
            affected_orders=[
                {
                    "order_number": o.order_number,
                    "customer_name": o.customer_name_snapshot,
                    "status": o.status,
                }
                for o in affected_orders.values()
            ],
        )

    with transaction.atomic():
        trading_day.is_open = day_values["is_open"]
        trading_day.daily_order_cap = day_values["daily_order_cap"]
        trading_day.cutoff_time = day_values["cutoff_time"]
        trading_day.window_start = day_values["window_start"]
        trading_day.window_end = day_values["window_end"]
        trading_day.notes_internal = day_values["notes_internal"]
        trading_day.save(
            update_fields=[
                "is_open", "daily_order_cap", "cutoff_time",
                "window_start", "window_end", "notes_internal",
            ]
        )
        for slot, new_capacity, closed in slot_updates:
            slot.capacity = new_capacity
            slot.is_closed = closed
            slot.save(update_fields=["capacity", "is_closed"])
        for dish, available, max_units in dish_updates:
            DayDishAvailability.objects.update_or_create(
                trading_day=trading_day, dish=dish,
                defaults={"is_available": available, "max_units": max_units},
            )

    trading_day.refresh_from_db()
    return JsonResponse(_state_json(target_date, trading_day))


# ---------------------------------------------------------------- entry point


@staff_login_required_json
@require_http_methods(["GET", "POST"])
@csrf_protect
def daily_controls_json(request: HttpRequest, date: str) -> JsonResponse:
    """`GET/POST /api/v1/staff/days/<date>/` — §12.8's daily controls,
    reshaped for the app. `GET` returns the current state (auto-
    materialising the `TradingDay` row via `core.materialise.materialise_day`
    exactly like the web view does, so browsing to a not-yet-materialised
    future date behaves the same on both surfaces); `POST` validates and
    saves, returning the same shape as `GET` on success. Any staff role.
    """
    try:
        target_date = dt.date.fromisoformat(date)
    except ValueError:
        return _error_response("not_found", "Invalid date.")

    settings = Settings.current()
    trading_day = materialise_day(target_date, settings)

    if request.method == "POST":
        return _post(request, target_date, trading_day)
    return JsonResponse(_state_json(target_date, trading_day))
