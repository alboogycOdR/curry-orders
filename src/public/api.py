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

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from core import eft
from core import lookup as lookup_service
from core import menu as menu_queries
from core.capacity import CapacityError, CheckoutLine, ReservationRequest, reserve
from core.http import absolute_media_url
from core.materialise import materialise_days
from core.models import (
    ActorKind,
    CollectionMethod,
    Customer,
    IdempotencyKey,
    Order,
    OrderSource,
    OrderStatus,
    PaymentMethod,
    Settings,
    ThrottleEvent,
)
from core.phone import InvalidPhoneNumber, normalize_sa_mobile
from core.tz import now_sast
from public import customer_sessions
from public.views import (
    _LOOKUP_GENERIC_ERROR,
    _featured_dish,
    _order_status_context,
    _order_status_lookup,
    _orderable_day_list,
    _reorder_matched_lines,
    _slot_list_for_day,
    _status_copy,
)
from storage import service as storage_service


class _CleanedPayload(TypedDict, total=False):
    name: str
    mobile: str
    note: str
    date: dt.date
    slot_id: int
    payment_method: str
    collection_method: str
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
    "outside_horizon": 400,
    "throttled": 429,
    "upload_invalid": 400,
    "not_found": 404,
    "auth_required": 401,
    "throttled_login": 429,
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
    # isinstance(True, int) is True in Python — reject booleans explicitly.
    if not isinstance(slot_id, int) or isinstance(slot_id, bool):
        errors["slot_id"] = "Choose a collection slot."
    else:
        cleaned["slot_id"] = slot_id

    payment_method = data.get("payment_method")
    if payment_method not in (PaymentMethod.EFT, PaymentMethod.CASH):
        errors["payment_method"] = "Choose a payment method."
    else:
        cleaned["payment_method"] = str(payment_method)

    # Poster-variant addition (open question 2): optional, defaults to
    # direct collection. Broadsheet checkout doesn't send this field at
    # all, so it's validated only when present rather than required.
    collection_method = data.get("collection_method", CollectionMethod.DIRECT)
    if collection_method not in (CollectionMethod.DIRECT, CollectionMethod.UBER_COURIER):
        errors["collection_method"] = "Choose how you'll collect."
    else:
        cleaned["collection_method"] = str(collection_method)

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
            # isinstance(True/False, int) is True in Python — reject booleans.
            if not isinstance(dish_id, int) or isinstance(dish_id, bool):
                errors["lines"] = f"Line {i}: missing dish."
                break
            if (
                not isinstance(quantity, int)
                or isinstance(quantity, bool)
                or not (1 <= quantity <= 20)
            ):
                errors["lines"] = f"Line {i}: quantity must be 1-20."
                break
            if not isinstance(option_value_ids, list) or not all(
                isinstance(v, int) and not isinstance(v, bool) for v in option_value_ids
            ):
                errors["lines"] = f"Line {i}: malformed options."
                break
            # Dedupe option_value_ids — duplicate values could be used to apply
            # a price modifier (delta) multiple times.
            deduped_ids = list(dict.fromkeys(option_value_ids))
            lines.append(CheckoutLine(
                dish_id=dish_id, quantity=quantity, option_value_ids=deduped_ids,
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
        collection_method=cleaned.get("collection_method", CollectionMethod.DIRECT),
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
            "outside_horizon", "date is outside the orderable range.", field="date",
        )

    trading_day = materialise_days(selected_date, settings, count=1)[0]

    # `dish_photo_url()` (core.menu) returns a *relative* `/media/...`
    # path whenever neither CDN_BASE_URL nor S3_PUBLIC_ENDPOINT is
    # configured (storage.service.public_dish_image_url's local-storage
    # fallback branch) -- exactly this deploy's current config. That's
    # fine for order.js, this same view's web consumer: a browser
    # resolves a root-relative `<img src>` against the page's own
    # origin automatically. It is NOT fine for the Flutter app
    # (docs/mobile/FLUTTER_APP_PLAN.md Phase 1's other consumer, aliased
    # verbatim onto this same view) -- `Image.network()` has no "page
    # origin" to resolve against, and silently, repeatedly fails to
    # load a relative URL. Found live 2026-09-15: the Menu screen showed
    # category chips (parsed from this same response) but zero dish
    # cards -- a `flutter test` repro against this endpoint's real
    # payload showed the failed loads triggering enough exceptions that
    # the widget tree never settled into a rendered frame.
    #
    # `core.http.absolute_media_url` (not a plain `request.
    # build_absolute_uri()`) -- see that function's own docstring for a
    # SECOND bug this same day: a naive absolute URL still comes out
    # `http://` on this HTTPS domain (DJANGO_TLS=false doesn't trust
    # Caddy's X-Forwarded-Proto), which a real Android device silently
    # refuses once cleartext is disabled -- invisible in a `flutter
    # test` repro, which doesn't enforce that OS-level policy.

    # with_options=True: additive over this endpoint's pre-existing shape
    # (order.js, the web consumer, ignores unknown fields) — the Flutter
    # app needs `options` to render a Spice/Extras configurator before
    # adding a dish with required options to the basket
    # (docs/mobile/FLUTTER_APP_PLAN.md Phase 3's "dish option configurator"
    # gap). Same {id, name, required, values:[{id, name, price_delta_cents}]}
    # shape `_menu_catalog_payload`/`api_day_availability` already use.
    dishes = menu_queries.dishes_for_date(trading_day, with_options=True)
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
                        "slug": dish.slug,
                        "name": dish.name,
                        "short_description": dish.short_description,
                        "price_cents": dish.price_cents,
                        "sold_out": dish.sold_out,
                        "photo_url": absolute_media_url(request, dish.photo_url),
                        "portion_label": dish.portion_label,
                        "category": dish.category,
                        "options": [
                            {
                                "id": opt.id,
                                "name": opt.name,
                                "required": opt.required,
                                "values": [
                                    {
                                        "id": v.id,
                                        "name": v.name,
                                        "price_delta_cents": v.price_delta_cents,
                                    }
                                    for v in (opt.values or [])
                                    if v.is_available
                                ],
                            }
                            for opt in (dish.options or [])
                        ],
                    }
                    for dish in category_dishes
                ],
            }
            for category_name, category_dishes in categories
        ],
        "slots": slots,
    })


@require_GET
def featured(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/featured/` — the "this week's special" hero dish
    (poster web home page's own hero card, `public.views.home`'s
    `featured`/`featured_photo_url` context). Added 2026-09-15: the app
    had no way to show this at all — its Home screen only ever showed
    the bare collection-status card, missing the one thing the web
    home page leads with. Same selection precedence as the web
    (`public.views._featured_dish`: `?featured=<slug>` query param,
    else `Dish.is_featured`, else a hardcoded fallback slug, else "just
    pick something") -- deliberately date-independent, same as the web
    (a single global "this week's special", not scoped to one
    collection day), so this endpoint takes no `date` param.
    """
    active = menu_queries.active_dishes()
    dish = _featured_dish(active, request.GET.get("featured"))
    if dish is None:
        return JsonResponse({"dish": None})
    return JsonResponse({
        "dish": {
            "id": dish.id,
            "slug": dish.slug,
            "name": dish.name,
            "short_description": dish.short_description,
            "price_cents": dish.price_cents,
            "photo_url": absolute_media_url(request, menu_queries.dish_photo_url(dish)),
            "portion_label": dish.portion_label,
            "category": dish.category,
        },
    })


# ---------------------------------------------------------------- Flutter app (Phase 1)
#
# docs/mobile/FLUTTER_APP_PLAN.md Phase 1 — JSON endpoints the Android
# app needs that the web build never did (it always had a server-rendered
# page instead). Auth is the existing Django session cookie
# (`public.customer_sessions`, unchanged) — no separate token scheme.
# The app calls `csrf_cookie` once to receive `csrftoken`, then echoes it
# back as `X-CSRFToken` on every POST, same mechanism the web JS uses via
# `getCookie('csrftoken')`, just fetched explicitly since no Django
# template is ever rendered client-side to embed one in.
#
# Everything else here reuses the exact same `core`/`public.views`
# helpers the web views call — no parallel business logic, only a
# different response format (JSON, not a template).


@ensure_csrf_cookie
@require_GET
def csrf_cookie(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/csrf/` — sets the `csrftoken` cookie. Call once at
    app start (and again on a 403 `csrf_failed`) before any POST below.
    """
    return JsonResponse({"ok": True})


@require_GET
def orderable_days_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/days/` — the orderable day list (§11.3's own
    `orderable_dates` listing), same `{index, iso, dow, dom, long}` shape
    `public.views._orderable_day_list` already builds for the web's date
    switcher. The app needs this to know *which* dates are worth calling
    `GET /api/v1/availability/?date=` for — that endpoint only rejects a
    date outside the raw preorder-days horizon, not one that's closed or
    already past today's cutoff (a real distinct concept — see
    `core.tz.orderable_dates`).
    """
    settings = Settings.current()
    today = now_sast().date()
    return JsonResponse({"days": _orderable_day_list(today, settings)})


def _order_json(order: Order, ctx: dict) -> dict:
    """Serialise one order using the exact context `_order_status_context`
    already computed (status copy, stepper, EFT-panel gating) — shared by
    `order_status_json` and `lookup_json` below so both return the same
    shape for the same order.
    """
    settings: Settings = ctx["settings"]
    lines = [
        {
            "dish_name": line.dish_name_snapshot,
            "unit_price_cents": line.unit_price_cents_snapshot,
            "quantity": line.quantity,
            "line_total_cents": line.line_total_cents,
            "options": line.options_snapshot,
            "kitchen_note": line.kitchen_note or "",
        }
        for line in ctx["lines"]
    ]

    payload: dict[str, object] = {
        "order_number": order.order_number,
        "public_token": order.public_token,
        "status": order.status,
        "status_copy": ctx["status_copy"],
        "step_data": ctx["step_data"],
        "is_terminal": ctx["is_terminal"],
        "can_reorder": ctx["can_reorder"],
        "payment_method": order.payment_method,
        "collection_method": order.collection_method,
        "collection_date": order.trading_day.date.isoformat() if order.trading_day_id else None,
        "collection_slot_label": (
            f"{order.slot.start_at.strftime('%H:%M')}–{order.slot.end_at.strftime('%H:%M')}"
            if order.slot_id else None
        ),
        "total_cents": order.total_cents,
        "note": order.note or "",
        "lines": lines,
    }
    if ctx["show_address"]:
        payload["collection_address_line"] = settings.collection_address_line or ""
        payload["collection_instructions"] = settings.collection_instructions or ""
    if ctx["show_eft_panel"]:
        payload["eft"] = {
            "bank_name": settings.bank_name or "",
            "account_name": settings.account_name or "",
            "account_number": settings.account_number or "",
            "branch_code": settings.branch_code or "",
            "account_type": settings.account_type or "",
            "reference": order.order_number,
            "amount_cents": order.total_cents,
            "hold_expires_at": order.hold_expires_at.isoformat() if order.hold_expires_at else None,
            "proof_already_uploaded": ctx["proof_already_uploaded"],
        }
    return payload


@require_GET
def order_status_json(request: HttpRequest, public_token: str) -> JsonResponse:
    """`GET /api/v1/orders/<token>/` — JSON equivalent of
    `public.views.order_status`'s server-rendered page. Reuses that
    view's exact query/context (`_order_status_lookup`/
    `_order_status_context`) — same status copy, EFT panel gating,
    five-dot stepper — only the output format differs.
    """
    order = _order_status_lookup(public_token)
    if order is None:
        return _error_response("not_found", "No such order.")
    return JsonResponse(_order_json(order, _order_status_context(order)))


@require_POST
@csrf_protect
def lookup_json(request: HttpRequest) -> JsonResponse:
    """`POST /api/v1/lookup/` — JSON equivalent of `public.views.lookup`
    (§11.10). Same throttling/generic-error discipline: every failure
    returns the same generic message so this endpoint can't be used to
    enumerate order numbers or confirm a mobile number belongs to anyone.

    Body: `{"order_number": "CT-...", "mobile": "082..."}` —
    `order_number` optional; when blank, returns up to 5 recent orders
    for the *signed-in* customer's own mobile (session cookie required —
    same guard as the web lookup's mobile-only listing; an app user is
    expected to use `GET /api/v1/account/orders/` for their own history
    instead of this path, see docs/mobile/FLUTTER_APP_PLAN.md Phase 3's
    IA note — this stays mainly for tracking a guest order).
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _error_response("validation_error", "Malformed JSON body.")
    if not isinstance(data, dict):
        return _error_response("validation_error", "Malformed JSON body.")

    order_number_input = str(data.get("order_number", "")).strip()
    mobile_input = str(data.get("mobile", ""))
    ip = request.META.get("REMOTE_ADDR") or "unknown"

    try:
        lookup_service.check_lookup_throttle(ip, order_number_input)
    except lookup_service.LookupError:
        return _error_response("throttled", _LOOKUP_GENERIC_ERROR)

    if order_number_input:
        order = lookup_service.find_order(order_number_input, mobile_input)
        lookup_service.record_lookup_attempt(ip, order_number_input)
        if order is None:
            return _error_response("not_found", _LOOKUP_GENERIC_ERROR)
        return JsonResponse({"orders": [_order_json(order, _order_status_context(order))]})

    customer = request.customer_user
    customer_digits = (customer.mobile_e164 or "")[-9:] if customer and customer.mobile_e164 else ""
    submitted_digits = lookup_service.last9_digits(mobile_input)
    if not customer:
        return _error_response(
            "auth_required",
            "Sign in to view all your orders by mobile number, or provide an order number.",
        )
    if not customer_digits or submitted_digits != customer_digits:
        return _error_response("not_found", _LOOKUP_GENERIC_ERROR)

    lookup_service.record_lookup_attempt(ip, "")
    found = lookup_service.find_orders_by_mobile(mobile_input, limit=5)
    if not found:
        return _error_response("not_found", _LOOKUP_GENERIC_ERROR)
    return JsonResponse({
        "orders": [_order_json(o, _order_status_context(o)) for o in found],
    })


_LOGIN_THROTTLE_LIMIT = 10
_LOGIN_THROTTLE_WINDOW_SECONDS = 3600  # 1 hour — same bucket/scope as the web login throttle.
_LOGIN_IP_SCOPE = "login_ip"


def _customer_json(customer: Customer) -> dict:
    return {"full_name": customer.full_name, "mobile_e164": customer.mobile_e164}


@require_POST
@csrf_protect
def login_json(request: HttpRequest) -> JsonResponse:
    """`POST /api/v1/auth/login/` — password login only. **v1 Account is
    password login, not OTP** (root CLAUDE.md) — no Send-code/magic-link
    endpoint exists here and none should be added. Shares the
    `login_ip` throttle scope/limit with `public.views.customer_login`
    (10/hour) so a brute-force attempt is capped across both web and app
    clients against the same bucket. On success, logs the customer into
    the same Django session `public.customer_sessions.log_in` uses for
    the web — the app carries that cookie on every later request.

    Body: `{"mobile": "082...", "password": "..."}`.
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _error_response("validation_error", "Malformed JSON body.")
    if not isinstance(data, dict):
        return _error_response("validation_error", "Malformed JSON body.")

    ip = request.META.get("REMOTE_ADDR") or "unknown"
    window_start = now_sast() - dt.timedelta(seconds=_LOGIN_THROTTLE_WINDOW_SECONDS)
    recent_failures = ThrottleEvent.objects.filter(
        scope=_LOGIN_IP_SCOPE, key=ip, occurred_at__gte=window_start,
    ).count()
    if recent_failures >= _LOGIN_THROTTLE_LIMIT:
        return _error_response(
            "throttled_login", "Too many sign-in attempts — try again in an hour.",
        )

    try:
        mobile = normalize_sa_mobile(str(data.get("mobile", "")))
    except InvalidPhoneNumber:
        mobile = ""
    password = str(data.get("password", ""))
    customer = Customer.objects.filter(mobile_e164=mobile, anonymised_at__isnull=True).first()
    if (
        not customer
        or not customer.password_hash
        or not check_password(password, customer.password_hash)
    ):
        ThrottleEvent.objects.create(scope=_LOGIN_IP_SCOPE, key=ip)
        return _error_response(
            "validation_error", "We couldn't sign you in. Check your mobile number and password.",
        )

    customer_sessions.log_in(request, customer)
    return JsonResponse(_customer_json(customer))


@require_POST
@csrf_protect
def signup_json(request: HttpRequest) -> JsonResponse:
    """`POST /api/v1/auth/signup/` — mirrors `public.views.customer_signup`
    field-for-field: name (2+ chars), SA mobile, password (8+ chars),
    and the same account-takeover guard for a mobile number that already
    has a guest order history (no OTP exists in v1 to verify ownership,
    so a pre-existing guest `Customer` row is rejected with a
    contact-us message rather than silently claimed).

    Body: `{"name": "...", "mobile": "082...", "password": "..."}`.
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _error_response("validation_error", "Malformed JSON body.")
    if not isinstance(data, dict):
        return _error_response("validation_error", "Malformed JSON body.")

    name = str(data.get("name", "")).strip()
    password = str(data.get("password", ""))
    try:
        mobile = normalize_sa_mobile(str(data.get("mobile", "")))
    except InvalidPhoneNumber:
        return _error_response(
            "validation_error", "Enter a valid South African mobile number.", field="mobile",
        )
    if len(name) < 2:
        return _error_response("validation_error", "Enter your name.", field="name")
    if len(password) < 8:
        return _error_response(
            "validation_error", "Use at least 8 characters for your password.", field="password",
        )

    customer, created = Customer.objects.get_or_create(
        mobile_e164=mobile, defaults={"full_name": name},
    )
    if customer.password_hash:
        return _error_response(
            "validation_error", "An account already exists for that mobile number.", field="mobile",
        )
    if not created:
        return _error_response(
            "validation_error",
            "You have already placed an order with this number. Use Order Lookup to view "
            "your orders — or contact us if you need help setting up an account.",
            field="mobile",
        )

    customer.full_name = name
    customer.password_hash = make_password(password)
    customer.save(update_fields=["full_name", "password_hash"])
    customer_sessions.log_in(request, customer)
    return JsonResponse(_customer_json(customer), status=201)


@require_POST
@csrf_protect
def logout_json(request: HttpRequest) -> JsonResponse:
    """`POST /api/v1/auth/logout/`."""
    customer_sessions.log_out(request)
    return JsonResponse({"ok": True})


@require_GET
def account_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/account/` — the signed-in customer's own profile.
    401 `auth_required` (not a redirect — there's no login *page* to
    redirect to from a native client) when there's no valid session.
    """
    customer = request.customer_user
    if customer is None:
        return _error_response("auth_required", "Sign in to view your account.")
    last_order = (
        Order.objects.filter(
            customer_mobile_snapshot=customer.mobile_e164, status=OrderStatus.COLLECTED,
        )
        .order_by("-created_at")
        .first()
    )
    payload = _customer_json(customer)
    payload["last_order"] = (
        {"order_number": last_order.order_number, "public_token": last_order.public_token}
        if last_order else None
    )
    return JsonResponse(payload)


@require_GET
def reorder_json(request: HttpRequest, public_token: str) -> JsonResponse:
    """`GET /api/v1/orders/<token>/reorder/` — the app's equivalent of
    `public.views.reorder`'s page: same re-matching rules
    (`_reorder_matched_lines`, current prices, drop archived/deactivated
    dishes and options with no live match), but returns plain JSON lines
    the app feeds straight into `basketProvider` instead of seeding the
    web's `localStorage` cart.

    404 `not_found` for a missing order; 422 `illegal_transition` for one
    that isn't `collected` yet (§11.11: only a collected order can be
    reordered — reusing that Appendix C code rather than inventing a new
    one, since it's the same "not in the right status for this action"
    shape every other transition-guard error in this API already uses).
    """
    order = Order.objects.filter(public_token=public_token).prefetch_related(
        "lines__dish__options__values",
    ).first()
    if order is None:
        return _error_response("not_found", "No such order.")
    if order.status != OrderStatus.COLLECTED:
        return _error_response("illegal_transition", "Only a collected order can be reordered.")

    matched, dropped = _reorder_matched_lines(order)
    if not matched:
        return _error_response(
            "not_found", "None of this order's dishes are still available to reorder.",
        )

    return JsonResponse({
        "lines": [
            {
                "dish_id": entry["dish"].pk,
                "dish_name": entry["dish"].name,
                "quantity": entry["quantity"],
                "option_value_ids": entry["option_ids"],
                "options_summary": ", ".join(v.name for v in entry["matched_values"]),
                "unit_price_cents": entry["unit_price_cents"],
            }
            for entry in matched
        ],
        "dropped_dish_names": dropped,
    })


@require_GET
def account_orders_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/account/orders/` — order history for the signed-in
    customer (app Orders tab / reorder support). 401 `auth_required`
    when not signed in — same guard as `account_json`. Lighter payload
    than `order_status_json` (no lines/EFT/stepper detail) — the app is
    expected to fetch the full detail on tap via
    `GET /api/v1/orders/<token>/`.
    """
    customer = request.customer_user
    if customer is None:
        return _error_response("auth_required", "Sign in to view your orders.")
    orders = (
        Order.objects.filter(customer_mobile_snapshot=customer.mobile_e164)
        .order_by("-created_at")[:20]
    )
    return JsonResponse({
        "orders": [
            {
                "order_number": o.order_number,
                "public_token": o.public_token,
                "status": o.status,
                "status_copy": _status_copy(o),
                "total_cents": o.total_cents,
                "created_at": o.created_at.isoformat(),
            }
            for o in orders
        ],
    })
