"""The one public JSON API endpoint this pass builds: `POST /api/checkout`
(spec §11.6, §17.3). Everything else in §17.3's public API table
(`/api/dates`, `/api/menu`, `/api/availability`, ...) is still served by
the plain server-rendered pages (`public/views.py`) — this exists because
checkout is the one action that needs a real transactional response
(success/failure, an error code, a redirect target), not because the
project is moving to a JSON-API-first architecture wholesale.

Field validation (this module, §11.6's table, 400 on failure) is
deliberately separate from capacity validation (`core.capacity.reserve()`,
422/403 — Appendix C) — different HTTP layers, same split the spec itself
draws in §11.6's own two-step list ("1. Validate fields... 2. Run §8.3
transaction").
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import TypedDict

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from core.capacity import CapacityError, CheckoutLine, ReservationRequest, reserve
from core.materialise import materialise_days
from core.models import IdempotencyKey, OrderSource, PaymentMethod, Settings
from core.phone import InvalidPhoneNumber, normalize_sa_mobile
from core.tz import now_sast


class _CleanedPayload(TypedDict, total=False):
    name: str
    mobile: str
    note: str
    date: dt.date
    slot_id: int
    payment_method: str
    lines: list[CheckoutLine]

# Appendix C's own table: which HTTP status each CapacityError code maps
# to. Everything not listed here is a 422 (§8.2's ceilings, the default).
_ERROR_STATUS = {
    "after_cutoff_disabled": 403,
    "reason_required": 403,
    "owner_only": 403,
    "stale_state": 409,
    "illegal_transition": 409,
    "idempotency_conflict": 409,
    "validation_error": 400,
    "throttled": 429,
    "upload_invalid": 400,
}


def _error_response(code: str, message: str, **extra: object) -> JsonResponse:
    status = _ERROR_STATUS.get(code, 422)
    body = {"error": code, "message": message, **extra}
    return JsonResponse(body, status=status)


def _validate_payload(data: dict[str, object]) -> tuple[dict[str, str], _CleanedPayload]:
    """§11.6's field table. Returns `(errors, cleaned)` — `errors` is a
    `{field: message}` dict (empty means valid); `cleaned` only has
    meaningful values for fields that validated. Purely shape/format
    validation, no database access — "Collection date ∈ orderable_dates"
    and "Slot open with remaining capacity" are §8.2 capacity ceilings
    (422, `outside_horizon`/`cutoff_passed`/`slot_full`/...), not field
    validation (400); `reserve()` re-checks both, under lock, regardless
    of what this function decides.
    """
    errors: dict[str, str] = {}
    cleaned: _CleanedPayload = {}

    name = str(data.get("name", "")).strip()
    if not (2 <= len(name) <= 80):
        errors["name"] = "Full name must be 2-80 characters."
    else:
        cleaned["name"] = name

    try:
        cleaned["mobile"] = normalize_sa_mobile(str(data.get("mobile", "")))
    except InvalidPhoneNumber:
        errors["mobile"] = "Enter a valid South African mobile number."

    note = str(data.get("note") or "").strip()
    if len(note) > 200:
        errors["note"] = "Order note must be 200 characters or fewer."
    else:
        cleaned["note"] = note

    date_str = data.get("date")
    try:
        cleaned["date"] = dt.date.fromisoformat(str(date_str))
    except (TypeError, ValueError):
        errors["date"] = "Choose a collection date."

    slot_id = data.get("slot_id")
    if not isinstance(slot_id, int):
        errors["slot_id"] = "Choose a collection slot."
    else:
        cleaned["slot_id"] = slot_id

    payment_method = data.get("payment_method")
    if payment_method not in (PaymentMethod.EFT, PaymentMethod.CASH):
        errors["payment_method"] = "Choose a payment method."
    else:
        cleaned["payment_method"] = str(payment_method)

    if not data.get("accept_policies"):
        errors["accept_policies"] = "You must accept the policies to order."

    lines_in = data.get("lines")
    lines: list[CheckoutLine] = []
    if not isinstance(lines_in, list) or not lines_in:
        errors["lines"] = "Your order needs at least one item."
    else:
        for i, raw_line in enumerate(lines_in):
            if not isinstance(raw_line, dict):
                errors["lines"] = f"Line {i}: malformed."
                break
            dish_id = raw_line.get("dish_id")
            quantity = raw_line.get("quantity")
            option_value_ids = raw_line.get("option_value_ids", [])
            if not isinstance(dish_id, int):
                errors["lines"] = f"Line {i}: missing dish."
                break
            if not isinstance(quantity, int) or not (1 <= quantity <= 20):
                errors["lines"] = f"Line {i}: quantity must be 1-20."
                break
            if not isinstance(option_value_ids, list) or not all(
                isinstance(v, int) for v in option_value_ids
            ):
                errors["lines"] = f"Line {i}: malformed options."
                break
            lines.append(CheckoutLine(
                dish_id=dish_id, quantity=quantity, option_value_ids=option_value_ids,
                kitchen_note=str(raw_line.get("kitchen_note") or "")[:200],
            ))
        else:
            cleaned["lines"] = lines

    return errors, cleaned


@require_POST
@csrf_protect
def checkout(request: HttpRequest) -> JsonResponse:
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        return _error_response("validation_error", "Idempotency-Key header is required.")

    body_bytes = request.body
    request_hash = hashlib.sha256(body_bytes).digest()

    existing = IdempotencyKey.objects.filter(pk=idempotency_key).select_related("order").first()
    if existing is not None:
        if existing.request_sha256 != request_hash:
            return _error_response(
                "idempotency_conflict",
                "This Idempotency-Key was already used with a different request.",
            )
        order = existing.order
        if order is None:
            # The original request didn't succeed (no order was ever
            # attached) — nothing meaningful to replay; let it proceed
            # as a fresh attempt rather than returning a stale failure.
            pass
        else:
            return JsonResponse(
                {"order_number": order.order_number, "public_token": order.public_token,
                 "status": order.status},
                status=existing.response_status,
            )

    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _error_response("validation_error", "Malformed JSON body.")
    if not isinstance(data, dict):
        return _error_response("validation_error", "Malformed JSON body.")

    errors, cleaned = _validate_payload(data)
    if errors:
        return JsonResponse(
            {
                "error": "validation_error",
                "message": "Some fields need attention.",
                "fields": errors,
            },
            status=400,
        )

    settings = Settings.current()
    today = now_sast().date()
    # §7.5 lazy materialisation — the chosen date may be inside the
    # horizon but not yet have a TradingDay row (e.g. the scheduler's
    # daily tick hasn't run since this exact date entered the horizon).
    materialise_days(today, settings, count=settings.preorder_days + 1)

    req = ReservationRequest(
        trading_day_date=cleaned["date"],
        slot_id=cleaned["slot_id"],
        payment_method=cleaned["payment_method"],
        customer_name=cleaned["name"],
        customer_mobile_e164=cleaned["mobile"],
        lines=cleaned["lines"],
        note=cleaned["note"],
        source=OrderSource.WEBSITE,
    )

    try:
        # §8.3's own pseudocode inserts idempotency_keys inside the same
        # transaction as the order itself — reserve() already opens its
        # own transaction.atomic(); nesting it inside this outer one turns
        # that into a savepoint, so both commit (or roll back) together
        # rather than leaving a window where a retry could race in after
        # the order commits but before the idempotency key is recorded.
        with transaction.atomic():
            order = reserve(req, settings)
            IdempotencyKey.objects.create(
                key=idempotency_key, request_sha256=request_hash, order=order, response_status=201,
            )
    except CapacityError as exc:
        return _error_response(
            exc.code, exc.message,
            line_index=exc.line_index, alternatives=exc.alternatives or None,
        )

    return JsonResponse(
        {
            "order_number": order.order_number,
            "public_token": order.public_token,
            "status": order.status,
        },
        status=201,
    )
