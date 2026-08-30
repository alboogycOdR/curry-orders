"""Staff JSON API endpoints: the generic `POST /manage/api/orders/:id/
transition` (spec §17.3's staff table) backing every board's row
actions, plus two milestone-6 day-level endpoints that aren't a single
order's transition (`lock_prep_list`, `close_out_day`) — `core.
transitions.apply()` only ever touches one order at a time, by design
(§17.2), so a day-wide action needs its own small endpoint rather than
being shoehorned through it. Session-authed (`staff.sessions`) + CSRF,
same as every other staff POST in this project; the `{% csrf_token %}`
on `staff/payments.html`/`kitchen.html`/`collection.html` is what puts
the cookie these endpoints' callers read.

`transition` is a single generic endpoint rather than one route per
action, matching `core.transitions.apply()`'s own single-dispatcher
shape and the spec's literal `{action, expected_status, reason?,
payload?}` body — every action this project implements (§9.1's fifteen
non-checkout, non-EFT-upload rows) is reachable through it, even the
ones with no staff UI yet (see `core/transitions.py`'s module
docstring).
"""
from __future__ import annotations

import datetime as dt
import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from core.capacity import OCCUPYING_STATUSES
from core.models import ActorKind, Order, Slot, TradingDay
from core.transitions import Actor, TransitionError, apply
from core.transitions import close_out_day as _close_out_day
from core.tz import now_sast

from .decorators import staff_login_required

# Appendix C's own table, same split public/api.py's checkout endpoint
# uses — everything not listed here is a 422 (a §8.2-style capacity
# ceiling bridged from CapacityError by core.transitions.apply() itself,
# e.g. `slot_full`/`dish_qty_exceeded` from `reinstate`/`amend_items`).
# `not_found` isn't an Appendix C code (that table is domain/rule
# failures only) but needs a real status too.
_ERROR_STATUS = {
    "stale_state": 409,
    "illegal_transition": 409,
    "reason_required": 403,
    "owner_only": 403,
    "validation_error": 400,
    "not_found": 404,
}


def _error_response(code: str, message: str, **extra: object) -> JsonResponse:
    status = _ERROR_STATUS.get(code, 422)
    return JsonResponse({"error": code, "message": message, **extra}, status=status)


@staff_login_required
@require_POST
@csrf_protect
def transition(request: HttpRequest, order_id: int) -> JsonResponse:
    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        return _error_response("not_found", "No such order.")

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _error_response("validation_error", "Malformed JSON body.")
    if not isinstance(data, dict):
        return _error_response("validation_error", "Malformed JSON body.")

    action = data.get("action")
    expected_status = data.get("expected_status")
    if not isinstance(action, str) or not isinstance(expected_status, str):
        return _error_response(
            "validation_error", "action and expected_status are required.",
        )
    reason = data.get("reason")
    if reason is not None and not isinstance(reason, str):
        return _error_response("validation_error", "reason must be a string.")
    payload = data.get("payload") or {}
    if not isinstance(payload, dict):
        return _error_response("validation_error", "payload must be an object.")

    actor = Actor(kind=ActorKind.STAFF, user=request.staff_user)
    try:
        order = apply(order, action, actor, expected_status, reason=reason, payload=payload)
    except TransitionError as exc:
        return _error_response(exc.code, exc.message, **exc.extra)

    return JsonResponse({"order_number": order.order_number, "status": order.status})


@staff_login_required
@require_POST
@csrf_protect
def assign_order(request: HttpRequest, order_id: int) -> JsonResponse:
    """§12.2's "assign" row action — a plain toggle, not a full
    `core.transitions` action (assignment isn't a state-machine
    transition per §9.1, just `orders.assigned_user`): posting again
    while already assigned to yourself un-assigns it, so the same
    inbox-row button works both ways without a second endpoint.
    """
    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        return _error_response("not_found", "No such order.")

    if order.assigned_user_id == request.staff_user.pk:
        order.assigned_user = None
    else:
        order.assigned_user = request.staff_user
    order.save(update_fields=["assigned_user"])
    return JsonResponse({
        "assigned_user_id": order.assigned_user_id,
        "assigned_user_name": order.assigned_user.name if order.assigned_user else None,
    })


@staff_login_required
@require_POST
@csrf_protect
def lock_prep_list(request: HttpRequest, date: str) -> JsonResponse:
    """§12.4's "Lock prep list" — freezes `trading_day.kitchen_locked_at`
    so the kitchen board can flag anything verified/accepted afterwards
    under "Added after lock" (`staff/views.py`'s `kitchen` computes that
    band from this timestamp, not a stored per-order flag, so it stays
    correct no matter which transition put an order on the board).
    """
    try:
        trading_day = TradingDay.objects.get(pk=dt.date.fromisoformat(date))
    except (TradingDay.DoesNotExist, ValueError):
        return _error_response("not_found", "No such trading day.")

    if trading_day.kitchen_locked_at is None:
        trading_day.kitchen_locked_at = now_sast()
        trading_day.kitchen_locked_by = request.staff_user
        trading_day.save(update_fields=["kitchen_locked_at", "kitchen_locked_by"])

    return JsonResponse({"kitchen_locked_at": trading_day.kitchen_locked_at.isoformat()})


@staff_login_required
@require_POST
@csrf_protect
def close_out_day(request: HttpRequest, date: str) -> JsonResponse:
    """§12.5's "Close out day" button — every order still `ready` for
    this trading day -> `no_show`, then `closed_out_at` set. A no-op
    (200, `closed: 0`) before the grace deadline; `staff/views.py`'s
    `collection_board` only renders the button once that's passed
    anyway, so hitting this early only happens by a direct API call.
    """
    try:
        trading_day = TradingDay.objects.get(pk=dt.date.fromisoformat(date))
    except (TradingDay.DoesNotExist, ValueError):
        return _error_response("not_found", "No such trading day.")

    actor = Actor(kind=ActorKind.STAFF, user=request.staff_user)
    closed = _close_out_day(trading_day, actor)
    return JsonResponse({"closed": closed})


@staff_login_required
@require_POST
@csrf_protect
def move_all_orders(request: HttpRequest, date: str, slot_id: int) -> JsonResponse:
    """§12.8's "Move all to…" helper — daily controls' answer to closing
    a slot that still has occupying orders. Every occupying order on
    `slot_id` gets its own `change_slot` `apply()` call (own transaction/
    lock/audit row each, same reasoning as `close_out_day`'s per-order
    loop) to `to_slot_id`; a mid-loop failure (the target fills up, a
    stale_state race with some other staff action) doesn't roll back the
    ones that already moved — the response reports how many actually
    moved plus which ones didn't, rather than pretending it's all-or-
    nothing.
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _error_response("validation_error", "Malformed JSON body.")
    to_slot_id = data.get("to_slot_id") if isinstance(data, dict) else None
    if not isinstance(to_slot_id, int):
        return _error_response("validation_error", "to_slot_id is required.")

    try:
        trading_day = TradingDay.objects.get(pk=dt.date.fromisoformat(date))
    except (TradingDay.DoesNotExist, ValueError):
        return _error_response("not_found", "No such trading day.")
    if not Slot.objects.filter(pk=slot_id, trading_day=trading_day).exists():
        return _error_response("not_found", "No such slot.")

    orders = list(
        Order.objects.filter(slot_id=slot_id, status__in=OCCUPYING_STATUSES)
    )
    actor = Actor(kind=ActorKind.STAFF, user=request.staff_user)
    moved = 0
    failures: list[dict[str, object]] = []
    for order in orders:
        try:
            apply(
                order, "change_slot", actor, order.status,
                payload={"new_slot_id": to_slot_id},
            )
            moved += 1
        except TransitionError as exc:
            failures.append({"order_number": order.order_number, "error": exc.code})

    return JsonResponse({"moved": moved, "failures": failures})
