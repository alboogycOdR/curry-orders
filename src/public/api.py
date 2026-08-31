"""The public JSON API endpoints this project builds outside the plain
server-rendered pages (`public/views.py`): `POST /api/checkout` (spec
§11.6, §17.3) and `POST /api/orders/:token/proof` (§17.3, milestone 4).
`GET /api/availability?date=` (Monday-sprint Phase 1a, see
docs/MONDAY_SPRINT.md) is the first departure from that -- the order
screen (`order.js`) needs to refresh its own dishes/slots without a full
page reload when the customer changes their collection date, something
the server-rendered `/order/` page (which only ever renders the first
orderable day, `public/views.py::order()`) can't do on its own.

Spec §17.3's own table names `/api/menu?date=` (dishes) and
`/api/availability?date=` (slots) as two separate endpoints; this
implementation deliberately combines both into the one
`/api/availability` response instead. The order screen's day-chip click
is a single user action that needs both atomically -- two separate
fetches would leave a window where the dish list and slot grid disagree
about which date they're showing, exactly the class of bug this
endpoint exists to fix. `/api/menu?date=` as its own spec-named endpoint
is still unbuilt; nothing here blocks adding it later if something else
needs dishes without slots.

Everything else in §17.3's public API table (`/api/dates`, ...) is
still served by the server-rendered pages -- these endpoints exist
because they need either a real transactional response (checkout,
proof upload) or a same-page refresh a full reload can't give
(availability), not because the project is moving to a JSON-API-first
architecture wholesale.

Field validation (this module, §11.6's table, 400 on failure) is
deliberately separate from capacity validation (`core.capacity.reserve()`,
422/403 — Appendix C) — different HTTP layers, same split the spec itself
draws in §11.6's own two-step list ("1. Validate fields... 2. Run §8.3
transaction"). `upload_proof` draws the same line: `storage.service`
validates the *file* (type/size, 400 `upload_invalid`), `core.eft`
validates the *transition* (409 `illegal_transition`) and the throttle
(429 `throttled`).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import TypedDict

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from core import eft
from core import menu as menu_queries
from core.capacity import CapacityError, CheckoutLine, ReservationRequest, reserve
from core.materialise import materialise_days
from core.models import ActorKind, IdempotencyKey, Order, OrderSource, PaymentMethod, Settings
from core.phone import InvalidPhoneNumber, normalize_sa_mobile
from core.tz import now_sast
from public.views import _slot_list_for_day
from storage import service as storage_service


class _CleanedPayload(TypedDict, total=False):
    name: str
    mobile: str
    note: str
    date: dt.date
    slot_id: int
    payment_method: str
    lines: list[CheckoutLine]

# Appendix C's own table: which HTTP status each error code maps to.
# Everything not listed here is a 422 (§8.2's capacity ceilings, the
# default — CapacityError's whole vocabulary bar the four explicit
# entries it shares with this map). `not_found` isn't an Appendix C code
# (that table is domain/rule failures only) but needs a real status too.
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
    "not_found": 404,
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


@require_POST
@csrf_protect
def upload_proof(request: HttpRequest, public_token: str) -> JsonResponse:
    """`POST /api/orders/:token/proof` (§17.3) — multipart, one `file`
    field. Order: look the order up, check the throttle (before doing
    any real work), validate the file (400 `upload_invalid` on a bad
    type/size — doesn't spend throttle budget), *then* spend the
    throttle budget and attempt the transition (409 `illegal_transition`
    if the order has moved past `awaiting_eft`/`payment_review` since
    the page loaded).
    """
    order = Order.objects.filter(public_token=public_token).select_related("payment").first()
    if order is None:
        return _error_response("not_found", "No such order.")

    try:
        eft.check_proof_upload_throttle(public_token)
    except eft.EftError as exc:
        return _error_response(exc.code, exc.message, **exc.extra)

    upload = request.FILES.get("file")
    if upload is None:
        return _error_response(
            "upload_invalid", "Choose a file to upload.", detail="missing",
        )
    data = upload.read()

    try:
        mime_type = storage_service.validate_proof(data)
    except storage_service.InvalidUpload as exc:
        return _error_response("upload_invalid", str(exc), detail=exc.reason)

    storage_key = storage_service.store_proof_bytes(data, mime_type)
    eft.record_proof_upload_attempt(public_token)

    try:
        eft.record_proof_upload(
            order,
            storage_key=storage_key,
            mime_type=mime_type,
            byte_size=len(data),
            sha256=storage_service.sha256_digest(data),
            actor_kind=ActorKind.CUSTOMER,
        )
    except eft.EftError as exc:
        return _error_response(exc.code, exc.message, **exc.extra)

    return JsonResponse({"status": "payment_review"})


@require_GET
def availability(request: HttpRequest) -> JsonResponse:
    """`GET /api/availability?date=YYYY-MM-DD` — see this module's own
    docstring for why dishes and slots are combined into one response
    rather than spec §17.3's literal `/api/menu?date=` +
    `/api/availability?date=` split.

    Monday-sprint Phase 1a: fixes the order screen's stale-slot bug
    (docs/MONDAY_SPRINT.md) — `order.js`'s day-chip click hits this to
    refresh the dish list and slot grid for the newly chosen date,
    instead of leaving the first orderable day's dishes/slots on screen
    (and a now-invalid slot ID sitting in state) no matter which day
    chip is clicked.
    """
    date_param = request.GET.get("date")
    if not date_param:
        return _error_response("validation_error", "date is required.", field="date")
    try:
        selected_date = dt.date.fromisoformat(date_param)
    except ValueError:
        return _error_response("validation_error", "date must be YYYY-MM-DD.", field="date")

    settings = Settings.current()
    today = now_sast().date()
    # Same horizon clamp as dish_detail() -- an arbitrary date must not
    # be able to make this endpoint insert TradingDay rows without
    # bound. Unlike dish_detail(), a bad date here is a real error
    # (400), not a silent fall-back to today: order.js only ever
    # requests dates from the same orderable-day list the page itself
    # rendered, so this should never fire from ordinary use, and
    # silently substituting a different date than the one asked for
    # would just move the stale-data bug here instead of fixing it.
    if not (today <= selected_date <= today + dt.timedelta(days=settings.preorder_days)):
        return _error_response(
            "validation_error", "date is outside the orderable range.", field="date",
        )

    trading_day = materialise_days(selected_date, settings, count=1)[0]
    dishes = menu_queries.dishes_for_date(trading_day)
    categories = menu_queries.categories_ordered(dishes)
    slots = _slot_list_for_day(trading_day)

    return JsonResponse({
        "date": selected_date.isoformat(),
        "categories": [
            {
                "name": category_name,
                "portion_label": category_dishes[0].portion_label if category_dishes else "",
                "dishes": [
                    {
                        "id": dish.id,
                        "name": dish.name,
                        "short_description": dish.short_description,
                        "price_cents": dish.price_cents,
                        "sold_out": dish.sold_out,
                    }
                    for dish in category_dishes
                ],
            }
            for category_name, category_dishes in categories
        ],
        "slots": slots,
    })
