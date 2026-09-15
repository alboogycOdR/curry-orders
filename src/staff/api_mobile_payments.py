"""Staff mobile JSON for the Payments (EFT queue) and Calendar screens
(Phase 6's parallel staff-mode build — docs/mobile/FLUTTER_APP_PLAN.md).
Both views are read-only reshapes of the exact same query/grouping logic
`staff/views.py::payments_queue` and `staff/views.py::calendar` already
run for their server-rendered templates, reusing that module's own
`DISH_WARNING_THRESHOLD` constant rather than re-deriving it, so the two
surfaces can never quietly drift apart. Row actions (verify_eft,
reject_eft, extend_hold, expire_hold_now) are NOT here — the app calls
`staff.api.transition` (`/manage/api/orders/<id>/transition`) directly
for those, same as `static/js/payments.js` does.
"""
from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from core.capacity import OCCUPYING_STATUSES, dish_units_used
from core.materialise import materialise_days
from core.models import Order, OrderStatus, PaymentMethod, Settings, Slot, TradingDay
from core.tz import now_sast

from .api_mobile import staff_login_required_json
from .views import DISH_WARNING_THRESHOLD

# ---------------------------------------------------------------- payments (EFT queue)


def _slot_window(slot: Slot | None) -> str | None:
    if slot is None:
        return None
    return f"{slot.start_at.strftime('%H:%M')}–{slot.end_at.strftime('%H:%M')}"


def _payment_row(order: Order) -> dict[str, object]:
    return {
        "id": order.pk,
        "order_number": order.order_number,
        "customer_name": order.customer_name_snapshot,
        "total_cents": order.total_cents,
        "slot_window": _slot_window(order.slot) if order.slot_id else None,
        "hold_expires_at": order.hold_expires_at.isoformat() if order.hold_expires_at else None,
        "proof_uploaded": order.payment.current_proof_media_id is not None,
        "status": order.status,
    }


@require_GET
@staff_login_required_json
def payments_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/staff/payments/` — mirrors `staff.views.payments_queue`
    exactly: `awaiting_eft`/`payment_review` orders only, hold-expiry
    ascending (lapsed first) then slot start. Any staff role.
    """
    orders = (
        Order.objects.filter(status__in=[OrderStatus.AWAITING_EFT, OrderStatus.PAYMENT_REVIEW])
        .select_related("payment", "slot", "trading_day")
        .order_by("hold_expires_at", "slot__start_at")
    )
    return JsonResponse({
        "rows": [_payment_row(order) for order in orders],
        # Same "don't hardcode a second guess" reasoning as the web
        # template's own "Extend hold" tooltip (staff.views.payments_queue).
        "hold_extension_minutes": Settings.current().hold_extension_minutes,
    })


# ---------------------------------------------------------------- calendar


def _heat_tier(pct: float) -> str:
    if pct >= 90:
        return "high"
    if pct >= 50:
        return "mid"
    return "low"


@require_GET
@staff_login_required_json
def calendar_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/staff/calendar/` — mirrors `staff.views.calendar`
    exactly: the 8-day (today + 7) grid via `core.materialise.materialise_days`,
    same per-day/per-slot occupancy counts and >=80%-of-`max_units` dish
    warnings. Read-only aggregation. Any staff role.
    """
    settings = Settings.current()
    today = now_sast().date()
    trading_days: list[TradingDay] = materialise_days(today, settings, count=8)

    days = []
    for td in trading_days:
        occupying = Order.objects.filter(trading_day=td, status__in=OCCUPYING_STATUSES).count()
        cash_occupying = Order.objects.filter(
            trading_day=td, payment_method=PaymentMethod.CASH, status__in=OCCUPYING_STATUSES,
        ).count()

        slots = []
        for s in td.slots.order_by("start_at"):
            s_occupying = Order.objects.filter(slot=s, status__in=OCCUPYING_STATUSES).count()
            pct = 100 * s_occupying / s.capacity if s.capacity else 0
            slots.append({
                "label": s.start_at.strftime("%H:%M"),
                "occupying": s_occupying,
                "capacity": s.capacity,
                "heat": _heat_tier(pct),
            })

        avail_rows = list(
            td.dish_availability.select_related("dish").filter(max_units__isnull=False)
        )
        dish_ids = [a.dish_id for a in avail_rows]
        used = dish_units_used(td, dish_ids) if dish_ids else {}
        dish_warnings = [
            {
                "dish_name": a.dish.name,
                "used_units": used.get(a.dish_id, 0),
                "max_units": a.max_units,
            }
            for a in avail_rows
            if a.max_units and used.get(a.dish_id, 0) / a.max_units >= DISH_WARNING_THRESHOLD
        ]

        days.append({
            "date": td.date.isoformat(),
            "dow_label": td.date.strftime("%a"),
            "is_open": td.is_open,
            "orders": {"value": occupying, "of": td.daily_order_cap},
            "cash": {"value": cash_occupying, "of": settings.cash_daily_cap},
            "slots": slots,
            "dish_warnings": dish_warnings,
        })

    return JsonResponse({"days": days})
