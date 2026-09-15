"""Staff mobile JSON for the Inbox and Kitchen desk boards (Phase 6,
"Screen 1"/"Screen 2" of the parallel staff-mode build —
docs/mobile/FLUTTER_APP_PLAN.md). Read-only: both views just reshape
the exact same query/grouping logic `staff/views.py::inbox` and
`staff/views.py::kitchen` already run for their server-rendered
templates into JSON, reusing that module's own constants
(`KITCHEN_BOARD_STATUSES`, `ASSISTED_SOURCES`, the recent-assisted
limit and recently-expired window) rather than re-deriving them, so the
two surfaces can never quietly drift apart. Row actions (assign,
accept/reject cash, reinstate, start_kitchen, mark_ready, lock prep
list) are NOT here — the app calls `staff.api`'s existing
`/manage/api/...` endpoints directly for those, same as the web boards'
own JS does.
"""
from __future__ import annotations

import datetime as dt

from django.db.models import Q
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from core.capacity import OCCUPYING_STATUSES
from core.models import Order, OrderStatus, PaymentMethod, Settings, Slot, TradingDay
from core.tz import now_sast

from .api_mobile import _error_response, staff_login_required_json
from .views import (
    _RECENT_ASSISTED_LIMIT,
    _RECENTLY_EXPIRED_WINDOW,
    ASSISTED_SOURCES,
    KITCHEN_BOARD_STATUSES,
)


def _slot_label(slot: Slot | None) -> str | None:
    if slot is None:
        return None
    return f"{slot.start_at.strftime('%H:%M')}–{slot.end_at.strftime('%H:%M')}"


def _inbox_row(order: Order) -> dict[str, object]:
    return {
        "id": order.pk,
        "order_number": order.order_number,
        "public_token": order.public_token,
        "customer_name": order.customer_name_snapshot,
        "customer_mobile_e164": order.customer_mobile_snapshot or None,
        "collection_date": order.trading_day.date.isoformat() if order.trading_day_id else None,
        "slot_label": _slot_label(order.slot) if order.slot_id else None,
        "status": order.status,
        "note": order.note or None,
        "assigned_user_name": order.assigned_user.name if order.assigned_user_id else None,
    }


# ---------------------------------------------------------------- inbox


@require_GET
@staff_login_required_json
def inbox_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/staff/inbox/` — mirrors `staff.views.inbox` exactly
    (same five queries/filters/orderings), reshaped into JSON rows via
    `_inbox_row` instead of a template context. Any staff role.
    """
    now = now_sast()
    settings = Settings.current()

    cash_requests = list(
        Order.objects.filter(status=OrderStatus.CASH_REQUEST)
        .select_related("slot", "trading_day", "assigned_user")
        .order_by("created_at")
    )

    hold_lapsed_eft = list(
        Order.objects.filter(status=OrderStatus.AWAITING_EFT, hold_expires_at__lt=now)
        .select_related("slot", "trading_day", "assigned_user")
        .order_by("hold_expires_at")
    )

    sla_deadline = now - dt.timedelta(minutes=settings.payment_review_sla_minutes)
    sla_breached = list(
        Order.objects.filter(status=OrderStatus.PAYMENT_REVIEW)
        .filter(
            Q(payment__proof_uploaded_at__lt=sla_deadline)
            | (Q(payment__proof_uploaded_at__isnull=True) & Q(created_at__lt=sla_deadline))
        )
        .select_related("slot", "trading_day", "payment", "assigned_user")
        .order_by("created_at")
    )
    hold_lapsed = hold_lapsed_eft + sla_breached

    orders_with_notes = list(
        Order.objects.filter(status__in=OCCUPYING_STATUSES)
        .exclude(note__isnull=True).exclude(note="")
        .select_related("slot", "trading_day", "assigned_user")
        .order_by("-created_at")[:30]
    )

    recent_assisted = list(
        Order.objects.filter(source__in=ASSISTED_SOURCES)
        .select_related("slot", "trading_day", "assigned_user")
        .order_by("-created_at")[:_RECENT_ASSISTED_LIMIT]
    )

    recently_expired = list(
        Order.objects.filter(
            status=OrderStatus.PAYMENT_EXPIRED, updated_at__gte=now - _RECENTLY_EXPIRED_WINDOW,
        )
        .select_related("slot", "trading_day", "assigned_user")
        .order_by("-updated_at")
    )

    sections = {
        "cash_requests": [_inbox_row(o) for o in cash_requests],
        "hold_lapsed": [_inbox_row(o) for o in hold_lapsed],
        "orders_with_notes": [_inbox_row(o) for o in orders_with_notes],
        "recent_assisted": [_inbox_row(o) for o in recent_assisted],
        "recently_expired": [_inbox_row(o) for o in recently_expired],
    }
    sections["is_empty"] = not any(sections.values())
    return JsonResponse(sections)


# ---------------------------------------------------------------- kitchen desk


def _parse_date_param(request: HttpRequest) -> dt.date | None:
    """Returns `None` (rather than falling back silently) on a malformed
    `?date=` so the caller can 400 instead of quietly showing today.
    """
    raw = request.GET.get("date")
    if not raw:
        return now_sast().date()
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return None


@require_GET
@staff_login_required_json
def kitchen_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/staff/kitchen/?date=YYYY-MM-DD` (default today) —
    mirrors `staff.views.kitchen`'s summary/exceptions/added-after-lock/
    tickets/meters exactly, reshaped into JSON. Any staff role.
    """
    date = _parse_date_param(request)
    if date is None:
        return _error_response("validation_error", "Invalid date.")

    settings = Settings.current()
    trading_day = TradingDay.objects.filter(pk=date).first()

    if trading_day is None:
        return JsonResponse({
            "date": date.isoformat(),
            "kitchen_locked_at": None,
            "meters": {
                "orders": {"value": 0, "of": 0},
                "cash": {"value": 0, "of": settings.cash_daily_cap},
            },
            "summary": [],
            "exceptions": [],
            "added_after_lock": [],
            "tickets": [],
        })

    board_orders = list(
        Order.objects.filter(trading_day=trading_day, status__in=KITCHEN_BOARD_STATUSES)
        .select_related("slot", "payment")
        .prefetch_related("lines__dish")
        .order_by("slot__start_at", "order_number")
    )

    summary_map: dict[tuple[str, str], dict[str, object]] = {}
    exceptions: list[dict[str, object]] = []
    for order in board_orders:
        order_lines = list(order.lines.all())
        for line in order_lines:
            key = (line.dish_name_snapshot, line.option_key)
            entry = summary_map.setdefault(key, {
                "dish_name": line.dish_name_snapshot,
                "option_summary": line.option_key,
                "quantity": 0,
                "order_numbers": [],
            })
            entry["quantity"] += line.quantity
            entry["order_numbers"].append(order.order_number)

        kitchen_note_lines = [line for line in order_lines if line.kitchen_note]
        allergen_lines = [line for line in order_lines if line.dish_id and line.dish.allergen_text]
        if order.note or kitchen_note_lines or allergen_lines:
            reason_parts: list[str] = []
            if order.note:
                reason_parts.append(f'Note: "{order.note}"')
            for line in kitchen_note_lines:
                reason_parts.append(f'{line.dish_name_snapshot}: "{line.kitchen_note}"')
            for line in allergen_lines:
                reason_parts.append(
                    f"{line.dish_name_snapshot} allergen: {line.dish.allergen_text}"
                )
            exceptions.append({
                "order_number": order.order_number,
                "reason_text": "; ".join(reason_parts),
            })

    summary = [
        summary_map[key]
        for key in sorted(summary_map.keys(), key=lambda k: (k[0], k[1]))
    ]

    added_after_lock: list[dict[str, object]] = []
    if trading_day.kitchen_locked_at is not None:
        added_after_lock = [
            _ticket(o) for o in board_orders
            if o.confirmed_at is not None and o.confirmed_at > trading_day.kitchen_locked_at
        ]

    tickets = [_ticket(o) for o in board_orders]

    occupying_today = Order.objects.filter(
        trading_day=trading_day, status__in=OCCUPYING_STATUSES,
    ).count()
    cash_occupying_today = Order.objects.filter(
        trading_day=trading_day, payment_method=PaymentMethod.CASH, status__in=OCCUPYING_STATUSES,
    ).count()

    return JsonResponse({
        "date": date.isoformat(),
        "kitchen_locked_at": (
            trading_day.kitchen_locked_at.isoformat() if trading_day.kitchen_locked_at else None
        ),
        "meters": {
            "orders": {"value": occupying_today, "of": trading_day.daily_order_cap},
            "cash": {"value": cash_occupying_today, "of": settings.cash_daily_cap},
        },
        "summary": summary,
        "exceptions": exceptions,
        "added_after_lock": added_after_lock,
        "tickets": tickets,
    })


def _ticket(order: Order) -> dict[str, object]:
    return {
        "id": order.pk,
        "order_number": order.order_number,
        "slot_label": _slot_label(order.slot) if order.slot_id else None,
        "customer_name": order.customer_name_snapshot,
        "items_summary": ", ".join(
            f"{line.quantity}× {line.dish_name_snapshot}" for line in order.lines.all()
        ),
        "payment_method": order.payment_method,
        "status": order.status,
    }
