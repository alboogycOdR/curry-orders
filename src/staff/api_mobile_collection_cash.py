"""Staff mobile JSON for the Collection board (§12.5) and the Cash
requests queue (§12.2/M7) — read-shaped mirrors of `staff.views.
collection_board`/`cash_requests`, same query/grouping/grace-deadline
logic, just JSON instead of a server-rendered template. Row actions
(`mark_ready`/`mark_collected`/`uncollect`/`close_out_no_show`/
`accept_cash`/`reject_cash`) are NOT here — the app POSTs those straight
to the existing `/manage/api/orders/<id>/transition` and
`/manage/api/days/<date>/close-out` endpoints (`staff/api.py`), same as
every other staff board.

Kept in its own module (rather than folded into `api_mobile_boards.py`)
per `staff/urls_api_mobile.py`'s own docstring: Phase 6 was built as
several independent screens in parallel, one file per group so two
agents never edit the same file at once.
"""
from __future__ import annotations

import datetime as dt

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from core.models import Order, OrderStatus, PaymentMethod, PaymentStatus, Settings, TradingDay
from core.tz import SAST, now_sast

from .api_mobile import staff_login_required_json

# Mirrors staff.views.COLLECTION_BOARD_STATUSES exactly (§9.3's own
# table) — never a second, drifting copy of "which three statuses".
COLLECTION_BOARD_STATUSES = [OrderStatus.READY, OrderStatus.IN_KITCHEN, OrderStatus.COLLECTED]


def _parse_date_param(request: HttpRequest) -> dt.date:
    raw = request.GET.get("date")
    if raw:
        try:
            return dt.date.fromisoformat(raw)
        except ValueError:
            pass
    return now_sast().date()


def _is_paid(order: Order) -> bool:
    """True once money has actually landed: EFT orders only ever reach
    this board already `verified` (via `verify_eft`); cash orders start
    `pending` (`accept_cash` doesn't touch payment.status) and only flip
    to `collected_cash` inside `mark_collected`'s cash branch. So this is
    `False` for an unpaid-so-far cash ticket and `True` for everything
    else, exactly the distinction the "CASH" vs "PAID" tag on the web
    board (`collection.html`) draws.
    """
    return order.payment.status in (PaymentStatus.VERIFIED, PaymentStatus.COLLECTED_CASH)


def _cash_amount_display(order: Order) -> str | None:
    """`null` for EFT tickets. For cash tickets, always a rand string —
    the *received* amount once `mark_collected`'s cash branch has set
    `cash_amount_received_cents`, otherwise the order's own total (the
    amount still due), same figure the web board's "CASH {{ total_cents
    }}" tag always shows regardless of collected status. The mobile
    Collected dialog parses this back to cents to prefill its prompt —
    see `collection_screen.dart`.
    """
    if order.payment_method != PaymentMethod.CASH:
        return None
    cents = order.payment.cash_amount_received_cents
    if cents is None:
        cents = order.total_cents
    return f"R {cents / 100:.2f}"


def _ticket_json(order: Order) -> dict[str, object]:
    return {
        "id": order.pk,
        "order_number": order.order_number,
        "customer_name": order.customer_name_snapshot,
        "item_count": order.lines.count(),
        "payment_method": order.payment_method,
        "cash_amount_display": _cash_amount_display(order),
        "is_paid": _is_paid(order),
        "status": order.status,
    }


@staff_login_required_json
@require_GET
def collection_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/staff/collection/?date=` — any staff role. Mirrors
    `staff.views.collection_board` exactly: grouped by slot in time
    order, current slot flagged, `ready` orders past
    `window_end + Settings.current().collection_grace_minutes` pulled
    into `uncollected` instead of their slot group. `can_close_out`
    mirrors that view's `past_deadline and not closed_out` gate for
    rendering its own "Close out day" button.
    """
    settings = Settings.current()
    date = _parse_date_param(request)
    trading_day = TradingDay.objects.filter(pk=date).first()

    if trading_day is None:
        return JsonResponse({
            "date": date.isoformat(),
            "slots": [],
            "uncollected": [],
            "can_close_out": False,
        })

    now = now_sast()
    deadline = dt.datetime.combine(
        trading_day.date, trading_day.window_end, tzinfo=SAST,
    ) + dt.timedelta(minutes=settings.collection_grace_minutes)
    past_deadline = now >= deadline

    orders = (
        Order.objects.filter(trading_day=trading_day, status__in=COLLECTION_BOARD_STATUSES)
        .select_related("payment", "slot")
        .prefetch_related("lines")
        .order_by("slot__start_at", "order_number")
    )

    current_slot = trading_day.slots.filter(start_at__lte=now.time(), end_at__gt=now.time()).first()
    current_slot_id = current_slot.pk if current_slot else None

    groups: dict[int, dict[str, object]] = {}
    uncollected: list[dict[str, object]] = []
    for order in orders:
        if past_deadline and order.status == OrderStatus.READY:
            uncollected.append(_ticket_json(order))
            continue
        group = groups.setdefault(order.slot_id, {"slot": order.slot, "tickets": []})
        group["tickets"].append(_ticket_json(order))
    slot_groups = sorted(groups.values(), key=lambda g: g["slot"].start_at)

    return JsonResponse({
        "date": date.isoformat(),
        "slots": [
            {
                "slot_id": g["slot"].pk,
                "start_at": g["slot"].start_at.strftime("%H:%M"),
                "end_at": g["slot"].end_at.strftime("%H:%M"),
                "is_now": g["slot"].pk == current_slot_id,
                "tickets": g["tickets"],
            }
            for g in slot_groups
        ],
        "uncollected": uncollected,
        "can_close_out": past_deadline and trading_day.closed_out_at is None,
    })


@staff_login_required_json
@require_GET
def cash_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/staff/cash/` — any staff role. Mirrors `staff.views.
    cash_requests` exactly: exactly `cash_request` orders, oldest first,
    no date filter (cash is same-day by nature).
    """
    orders = (
        Order.objects.filter(status=OrderStatus.CASH_REQUEST)
        .select_related("slot", "trading_day")
        .order_by("created_at")
    )
    return JsonResponse({
        "orders": [
            {
                "id": order.pk,
                "order_number": order.order_number,
                "customer_name": order.customer_name_snapshot,
                "total_cents": order.total_cents,
                "collection_date": order.trading_day.date.isoformat(),
                "slot_label": f"{order.slot.start_at:%H:%M}–{order.slot.end_at:%H:%M}",
            }
            for order in orders
        ],
    })
