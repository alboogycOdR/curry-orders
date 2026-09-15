"""Staff mobile JSON for the New assisted order screen (Phase 6 —
docs/mobile/FLUTTER_APP_PLAN.md). One endpoint, `assisted_order_json`,
handling both `GET` (form data for a given date) and `POST` (create the
order) on the same URL — mirrors `staff/views.py::assisted_order_new`
exactly: same field validation, and the exact same §8.3
`core.capacity.reserve()` transaction the public checkout API
(`public/api.py::checkout`) uses, via the same
`ReservationRequest`/`CheckoutLine` construction. Structural parity with
web checkout's capacity handling is the whole point of this screen (see
`assisted_order_new`'s own docstring) — nothing here builds a second,
different capacity-checking path.

Field validation errors are collected into a list (not just the first
failure) and returned together — same "top error list" UX
`assisted_order_form.html` renders (`{% for e in errors %}`), just
shaped as `{field, message}` pairs instead of plain strings so the app
can place each one next to its own field. `CapacityError` (raised by
`reserve()` itself for capacity/cutoff/cash ceilings — see
`core.capacity.check_after_cutoff_permission`/`check_cash`, which is
where the after-cutoff-reason and cash-enabled rules are actually
enforced, not a pre-check in this view) is mapped using the exact same
Appendix C status table `public/api.py`'s checkout endpoint uses, kept
as a local copy here since `api_mobile._ERROR_STATUS` (auth/validation/
lockout codes only) doesn't cover it.
"""
from __future__ import annotations

import datetime as dt
import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from core.capacity import CapacityError, CheckoutLine, ReservationRequest, reserve
from core.materialise import materialise_days
from core.menu import MenuDish, dishes_for_date
from core.models import ActorKind, OrderStatus, PaymentMethod, Settings, TradingDay, User
from core.notifications import notify_staff
from core.phone import InvalidPhoneNumber, normalize_sa_mobile
from core.transitions import Actor, TransitionError
from core.transitions import apply as apply_transition
from core.tz import now_sast

from .api_mobile import _error_response, staff_login_required_json
from .views import ASSISTED_SOURCES, _slot_rows_for_day

# Same table as `public/api.py`'s own `_ERROR_STATUS` — this endpoint's
# `reserve()` call can raise any Appendix C code that public checkout
# can, and D-11's after-cutoff codes (`after_cutoff_disabled`,
# `reason_required`) on top; everything not listed here is a 422 (§8.2's
# capacity ceilings), exactly like the public checkout view.
_CAPACITY_ERROR_STATUS = {
    "after_cutoff_disabled": 403,
    "reason_required": 403,
    "owner_only": 403,
    "stale_state": 409,
    "illegal_transition": 409,
    "idempotency_conflict": 409,
    "validation_error": 400,
    "outside_horizon": 400,
    "throttled": 429,
    "upload_invalid": 400,
    "not_found": 404,
    "auth_required": 401,
    "throttled_login": 429,
}


def _capacity_error_response(exc: CapacityError) -> JsonResponse:
    status = _CAPACITY_ERROR_STATUS.get(exc.code, 422)
    body: dict[str, object] = {"error": exc.code, "message": exc.message}
    if exc.line_index is not None:
        body["line_index"] = exc.line_index
    if exc.alternatives:
        body["alternatives"] = exc.alternatives
    return JsonResponse(body, status=status)


# ---------------------------------------------------------------- GET (form data)


def _dish_json(dish: MenuDish) -> dict[str, object]:
    return {
        "id": dish.id,
        "slug": dish.slug,
        "name": dish.name,
        "short_description": dish.short_description,
        "price_cents": dish.price_cents,
        "sold_out": dish.sold_out,
        "portion_label": dish.portion_label,
        "category": dish.category,
        "options": [
            {
                "id": option.id,
                "name": option.name,
                "required": option.required,
                "values": [
                    {
                        "id": value.id,
                        "name": value.name,
                        "price_delta_cents": value.price_delta_cents,
                        "is_available": value.is_available,
                    }
                    for value in option.values
                ],
            }
            for option in dish.options
        ],
    }


def _slot_json(row: dict) -> dict[str, object]:
    slot = row["slot"]
    return {
        "id": slot.pk,
        "label": f"{slot.start_at:%H:%M}–{slot.end_at:%H:%M}",
        "occupying": row["occupying"],
        "capacity": slot.capacity,
        "full": row["full"],
    }


def _get_response(
    settings: Settings,
    today: dt.date,
    selected_date: dt.date,
    trading_day: TradingDay,
    is_today: bool,
) -> JsonResponse:
    menu_dishes = dishes_for_date(trading_day, with_options=True)
    slot_rows = _slot_rows_for_day(trading_day)
    # D-11 / `core.capacity.check_after_cutoff_permission`: for a
    # same-day assisted order, when the setting is on, a reason is
    # mandatory (when off, same-day assisted ordering is refused
    # outright — no reason field would help, `assisted_after_cutoff_enabled`
    # on its own already tells the app to show that note instead).
    requires_after_cutoff_reason = is_today and settings.assisted_after_cutoff_enabled
    return JsonResponse({
        "date": selected_date.isoformat(),
        "min_date": today.isoformat(),
        "max_date": (today + dt.timedelta(days=settings.preorder_days)).isoformat(),
        "dishes": [_dish_json(d) for d in menu_dishes],
        "slots": [_slot_json(r) for r in slot_rows],
        "cash_enabled": settings.cash_enabled,
        "assisted_after_cutoff_enabled": settings.assisted_after_cutoff_enabled,
        "is_today": is_today,
        "requires_after_cutoff_reason": requires_after_cutoff_reason,
    })


# ---------------------------------------------------------------- POST (create)


def _post_response(
    request: HttpRequest,
    data: dict[str, object],
    settings: Settings,
    selected_date: dt.date,
    trading_day: TradingDay,
) -> JsonResponse:
    errors: list[dict[str, str]] = []

    def add_error(field: str, message: str) -> None:
        errors.append({"field": field, "message": message})

    customer_name = str(data.get("customer_name", "")).strip()
    if not (2 <= len(customer_name) <= 80):
        add_error("customer_name", "Customer name must be 2-80 characters.")

    customer_mobile = ""
    try:
        customer_mobile = normalize_sa_mobile(str(data.get("customer_mobile", "")))
    except InvalidPhoneNumber:
        add_error("customer_mobile", "Enter a valid South African mobile number.")

    note = str(data.get("note") or "").strip()
    if len(note) > 200:
        add_error("note", "Order note must be 200 characters or fewer.")

    source = data.get("source")
    if source not in ASSISTED_SOURCES:
        add_error("source", "Choose an order source.")

    payment_method = data.get("payment_method")
    if payment_method not in (PaymentMethod.EFT, PaymentMethod.CASH):
        add_error("payment_method", "Choose a payment method.")

    slot_id = data.get("slot_id")
    if not isinstance(slot_id, int) or isinstance(slot_id, bool):
        add_error("slot_id", "Choose a collection slot.")

    after_cutoff_reason = str(data.get("after_cutoff_reason") or "").strip()

    eft_mode = str(data.get("eft_mode") or "hold")
    eft_confirm_reason = str(data.get("eft_confirm_reason") or "").strip()
    if eft_mode == "confirmed_prep" and not eft_confirm_reason:
        add_error(
            "eft_confirm_reason",
            'A reason is required to confirm payment was already seen (D-18).',
        )

    # dish_id must be a real dish for this trading day — the web's own
    # per-dish POST-key loop only ever iterates `menu_dishes`, so an
    # unknown dish id can't arise there; a JSON body isn't shaped that
    # way, so it's checked explicitly here instead.
    menu_dish_ids = {d.id for d in dishes_for_date(trading_day, with_options=True)}
    lines_in = data.get("lines")
    lines: list[CheckoutLine] = []
    if isinstance(lines_in, list):
        for i, raw_line in enumerate(lines_in):
            if not isinstance(raw_line, dict):
                add_error("lines", f"Line {i}: malformed.")
                continue
            dish_id = raw_line.get("dish_id")
            quantity = raw_line.get("quantity")
            option_value_ids = raw_line.get("option_value_ids", [])
            dish_id_valid = isinstance(dish_id, int) and not isinstance(dish_id, bool)
            if not dish_id_valid or dish_id not in menu_dish_ids:
                add_error("lines", f"Line {i}: unknown dish.")
                continue
            if not isinstance(quantity, int) or isinstance(quantity, bool):
                add_error("lines", f"Line {i}: enter a whole number.")
                continue
            if quantity <= 0:
                # Same as assisted_order_new's own `if qty <= 0: continue`
                # — a zero/blank quantity row is just not a line, not an
                # error on its own.
                continue
            if not isinstance(option_value_ids, list) or not all(
                isinstance(v, int) and not isinstance(v, bool) for v in option_value_ids
            ):
                add_error("lines", f"Line {i}: malformed options.")
                continue
            deduped_ids = list(dict.fromkeys(option_value_ids))
            lines.append(
                CheckoutLine(dish_id=dish_id, quantity=quantity, option_value_ids=deduped_ids)
            )

    if not lines:
        add_error("lines", "Add at least one dish.")

    if errors:
        return _error_response(
            "validation_error", "Please fix the errors below.", errors=errors,
        )

    req = ReservationRequest(
        trading_day_date=selected_date,
        slot_id=slot_id,
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
        return _capacity_error_response(exc)

    # Same "new order" push public/api.py::checkout sends for a web
    # order — an assisted order is just as much a new order for
    # everyone else on shift to know about, even though the staff
    # member who placed it obviously already knows. Fired before the
    # EFT-escalation branch below, and regardless of whether that
    # branch succeeds -- the order itself exists either way.
    notify_staff(
        list(User.objects.filter(active=True)),
        title="New order",
        body=f"{order.order_number} — {req.customer_name}",
        data={"order_number": order.order_number, "type": "new_order"},
    )

    warning: str | None = None
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
            # Same partial-success case `assisted_order_new` handles with
            # a warning message + redirect to inbox -- the order exists,
            # just not escalated; surface both rather than turning an
            # already-created order into a hard failure response.
            warning = (
                f"Order {order.order_number} was created but couldn't be escalated: "
                f"{exc.message}"
            )
            order.refresh_from_db()

    body: dict[str, object] = {
        "order_number": order.order_number,
        "public_token": order.public_token,
        "status": order.status,
    }
    if warning:
        body["warning"] = warning
    return JsonResponse(body, status=201)


# ---------------------------------------------------------------- entry point


@staff_login_required_json
@require_http_methods(["GET", "POST"])
@csrf_protect
def assisted_order_json(request: HttpRequest) -> JsonResponse:
    """`GET/POST /api/v1/staff/orders/new/` — §12.9's assisted order
    entry, reshaped for the app. Any staff role. `GET ?date=YYYY-MM-DD`
    (default today) returns the form data for that day; `POST` creates
    the order. See this module's own docstring for the capacity-parity
    and error-shape notes.
    """
    settings = Settings.current()
    today = now_sast().date()

    data: dict[str, object] = {}
    if request.method == "POST":
        try:
            parsed = json.loads(request.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return _error_response("validation_error", "Malformed JSON body.")
        if not isinstance(parsed, dict):
            return _error_response("validation_error", "Malformed JSON body.")
        data = parsed
        date_param = str(data.get("date") or "") or today.isoformat()
    else:
        date_param = request.GET.get("date") or today.isoformat()

    try:
        selected_date = dt.date.fromisoformat(date_param)
    except ValueError:
        selected_date = today
    if not (today <= selected_date <= today + dt.timedelta(days=settings.preorder_days)):
        selected_date = today

    trading_day = materialise_days(selected_date, settings, count=1)[0]
    is_today = selected_date == today

    if request.method == "POST":
        return _post_response(request, data, settings, selected_date, trading_day)
    return _get_response(settings, today, selected_date, trading_day, is_today)
