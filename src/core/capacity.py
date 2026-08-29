"""The capacity engine (spec §8) — "This is the critical backend."

Every reservation change happens in one database transaction with row
locks (`SELECT ... FOR UPDATE`) on, in this fixed order: the
`trading_days` row, the `slots` row, then each affected
`day_dish_availability` row ordered by `dish_id`. Fixed lock ordering
prevents deadlocks between concurrent checkouts (§8's own opening line).

`core/` has no HTTP imports (§17.2) — `reserve()` raises `CapacityError`
(carrying the Appendix C error `code`) rather than returning an HTTP
response; the view layer (`public/api.py`) maps that to a 422/403 JSON
body. The individual `check_*` functions below are exposed separately,
not just inlined into `reserve()`, so `core.transitions` (milestone 5:
`reinstate`, `change_slot`, `amend_items` all re-run a subset of these
same ceilings per §9.1's table) can reuse them instead of duplicating
the rules.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Sum

if TYPE_CHECKING:
    from django.db.models import Count, Q

from .models import (
    ActorKind,
    Customer,
    DayDishAvailability,
    Dish,
    DishOptionValue,
    Order,
    OrderEvent,
    OrderLine,
    OrderSource,
    PaymentMethod,
    PaymentStatus,
    Settings,
    Slot,
    TradingDay,
    User,
)
from .models import Payment as PaymentModel
from .ordering import derive_option_key, format_order_number, generate_public_token, price_line
from .tz import now_sast

# §8.1: "Occupying set (day, slot and cash ceilings)" — every status that
# still holds capacity. `payment_expired`, `cancelled`, `collected` do not.
OCCUPYING_STATUSES = frozenset({
    "awaiting_eft", "payment_review", "cash_request",
    "confirmed_prep", "cash_due", "in_kitchen", "ready",
})


class CapacityError(Exception):
    """One Appendix C error. `code` is what the API layer maps to an HTTP
    status (422 for the §8.2 ceilings below, 403 for the after-cutoff/
    permission codes — that mapping lives in the view layer, not here).
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        line_index: int | None = None,
        alternatives: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.line_index = line_index
        self.alternatives = alternatives or {}


@dataclass
class CheckoutLine:
    dish_id: int
    quantity: int
    option_value_ids: list[int] = field(default_factory=list)
    kitchen_note: str = ""


@dataclass
class ReservationRequest:
    trading_day_date: dt.date
    slot_id: int
    payment_method: str  # PaymentMethod.EFT / .CASH
    customer_name: str
    # Already normalised E.164 (core.phone.normalize_sa_mobile) — field
    # validation is the caller's job (§11.6's step 1, "Validate fields
    # (400 on failure)"), not this transaction's; reserve() assumes valid
    # input, same division of labour as price_line() assumes current
    # prices are handed to it rather than looking them up itself.
    customer_mobile_e164: str
    lines: list[CheckoutLine]
    note: str = ""
    source: str = OrderSource.WEBSITE
    now: dt.datetime | None = None  # defaults to now_sast(); a param for tests
    # Assisted-order / staff-checkout fields (D-11, §9.1 "checkout"):
    created_by_user: User | None = None
    is_staff_assisted: bool = False
    after_cutoff_reason: str | None = None


# ---------------------------------------------------------------- ceiling checks (§8.2)


def check_day_open(trading_day: TradingDay) -> None:
    if not trading_day.is_open:
        raise CapacityError("day_closed", "That collection day isn't taking orders.")


def check_horizon(trading_day_date: dt.date, today: dt.date, preorder_days: int) -> None:
    if trading_day_date < today or trading_day_date > today + dt.timedelta(days=preorder_days):
        raise CapacityError(
            "outside_horizon", "That collection date is outside the ordering window."
        )


def check_cutoff(
    trading_day_date: dt.date, today: dt.date, now_sast_time: dt.time, cutoff_time: dt.time
) -> None:
    """Public checkout only (§8.2 ceiling 0's own "(public)" qualifier) —
    staff assisted orders go through `check_after_cutoff_permission`
    instead, which can bypass this per D-11.
    """
    if trading_day_date == today and now_sast_time >= cutoff_time:
        raise CapacityError("cutoff_passed", "Same-day ordering closed at the cut-off time.")


def check_after_cutoff_permission(
    settings: Settings, trading_day_date: dt.date, today: dt.date, after_cutoff_reason: str | None
) -> None:
    """D-11: "`assisted_after_cutoff_enabled` owner setting; when on, any
    staff with mandatory reason." Only relevant when an assisted order
    targets *today* after the cut-off would otherwise apply — a future
    date's assisted order never needs this (cutoff only ever applies to
    today).
    """
    if trading_day_date != today:
        return
    if not settings.assisted_after_cutoff_enabled:
        raise CapacityError("after_cutoff_disabled", "After-cut-off assisted orders are disabled.")
    if not after_cutoff_reason:
        raise CapacityError("reason_required", "A reason is required for an after-cut-off order.")


def check_slot_open(slot: Slot) -> None:
    if slot.is_closed:
        raise CapacityError("slot_closed", "That collection slot is closed.")


def check_day_cap(trading_day: TradingDay) -> None:
    occupying = Order.objects.filter(
        trading_day=trading_day, status__in=OCCUPYING_STATUSES
    ).count()
    if occupying >= trading_day.daily_order_cap:
        raise CapacityError(
            "day_full", "That day is fully booked.",
            alternatives=_next_open_date_alternative(trading_day),
        )


def check_slot_cap(slot: Slot) -> None:
    occupying = Order.objects.filter(slot=slot, status__in=OCCUPYING_STATUSES).count()
    if occupying >= slot.capacity:
        raise CapacityError(
            "slot_full", "That collection time is now full.",
            alternatives=_slot_alternatives(slot.trading_day_id),
        )


def dish_units_used(
    trading_day: TradingDay, dish_ids: list[int], *, exclude_order_id: int | None = None
) -> dict[int, int]:
    """§8.1's `v_dish_units_used`, as an ORM aggregate rather than a DB
    view — units on lines whose order is in the occupying set **or**
    has `dish_units_consumed = true` (D-03), grouped by dish. Called
    *after* the caller already holds the relevant row locks (this
    function takes no lock itself — a plain read is enough once the
    trading day/slot/availability rows are locked, since nothing else
    can insert a competing order against this trading day until this
    transaction commits).

    `exclude_order_id`: `core.transitions.amend_items` (milestone 5)
    rechecks ceilings for an order that already holds some of this same
    capacity — its own current lines would otherwise double-count
    against themselves when comparing the *new* quantity to what's
    left. Checkout (`reserve()`, no existing order yet) never needs
    this.
    """
    rows = (
        OrderLine.objects.filter(
            order__trading_day=trading_day,
            dish_id__in=dish_ids,
        )
        .filter(_occupying_or_consumed_q())
        .exclude(order_id=exclude_order_id if exclude_order_id is not None else -1)
        .values("dish_id")
        .annotate(units=Sum("quantity"))
    )
    return {row["dish_id"]: row["units"] for row in rows}


def _occupying_or_consumed_q() -> Q:
    from django.db.models import Q

    return Q(order__status__in=OCCUPYING_STATUSES) | Q(order__dish_units_consumed=True)


def check_dish_line(
    dish: Dish | None,
    avail: DayDishAvailability | None,
    used_units: dict[int, int],
    dish_id: int,
    quantity: int,
    line_index: int,
) -> None:
    """Ceiling 3, one order line. Mutates `used_units[dish_id]` on
    success so a second line for the same dish in the *same* order also
    respects the cap against the running total, not just the
    pre-checkout snapshot.
    """
    if dish is None or dish.archived_at is not None or not dish.is_active_on_menu:
        raise CapacityError(
            "dish_unavailable", "That dish is no longer available.", line_index=line_index
        )
    if avail is not None and not avail.is_available:
        raise CapacityError(
            "dish_unavailable", "That dish isn't available on this day.", line_index=line_index
        )

    max_units = avail.max_units if avail is not None else None
    if max_units is not None:
        already_used = used_units.get(dish_id, 0)
        if already_used + quantity > max_units:
            raise CapacityError(
                "dish_qty_exceeded", "Not enough of that dish left for this day.",
                line_index=line_index,
            )
        used_units[dish_id] = already_used + quantity


def check_cash(
    trading_day: TradingDay, settings: Settings, today: dt.date, payment_method: str
) -> None:
    if payment_method != PaymentMethod.CASH:
        return
    if not settings.cash_enabled:
        raise CapacityError("cash_not_allowed", "Cash isn't accepted at the moment.")
    if settings.cash_same_day_only and trading_day.date != today:
        raise CapacityError("cash_not_allowed", "Cash is only accepted for same-day collection.")
    cash_occupying = Order.objects.filter(
        trading_day=trading_day, payment_method=PaymentMethod.CASH, status__in=OCCUPYING_STATUSES
    ).count()
    if cash_occupying >= settings.cash_daily_cap:
        raise CapacityError("cash_cap", "The cash allowance for today is full.")


def _slot_alternatives(trading_day_id: dt.date) -> dict[str, object]:
    """Best-effort "next open slots on the same day" (Appendix C's own
    example). "next_open_date" (the other half of the example payload)
    would mean scanning forward across materialised trading days, which
    needs its own query plan this pass doesn't build — omitted rather
    than guessed at; `alternatives` is documented as "where computable".
    """
    open_slots = (
        Slot.objects.filter(trading_day_id=trading_day_id, is_closed=False)
        .annotate(occupying=_occupying_count_subquery())
    )
    slots = [
        {
            "slot_id": s.pk,
            "label": f"{s.start_at.strftime('%H:%M')}-{s.end_at.strftime('%H:%M')}",
            "remaining": s.capacity - (s.occupying or 0),
        }
        for s in open_slots
        if (s.capacity - (s.occupying or 0)) > 0
    ]
    return {"slots": slots} if slots else {}


def _occupying_count_subquery() -> Count:
    from django.db.models import Count, Q

    return Count("orders", filter=Q(orders__status__in=OCCUPYING_STATUSES))


def _next_open_date_alternative(trading_day: TradingDay) -> dict[str, object]:
    # See _slot_alternatives' docstring — same "not computed this pass" call.
    return {}


def _upsert_customer(mobile_e164: str, name: str, now: dt.datetime) -> Customer:
    """D-14: `customers.mobile_e164` unique; upsert; order-level
    snapshots. Not part of the fixed lock-ordering list (§8's own
    "trading_days, slots, day_dish_availability" — customers isn't a
    capacity table), so this runs after the ceiling checks rather than
    up front with the others; still inside the same transaction, so a
    rolled-back reservation never leaves a stray Customer row behind.
    """
    from django.db.models import F

    customer, created = Customer.objects.get_or_create(
        mobile_e164=mobile_e164,
        defaults={"full_name": name, "last_order_at": now, "order_count": 1},
    )
    if not created:
        customer.full_name = name  # latest name wins, same "snapshot per order" spirit as Order
        customer.last_order_at = now
        customer.order_count = F("order_count") + 1
        customer.save(update_fields=["full_name", "last_order_at", "order_count"])
        customer.refresh_from_db(fields=["order_count"])
    return customer


# ---------------------------------------------------------------- reservation transaction (§8.3)


def reserve(req: ReservationRequest, settings: Settings) -> Order:
    """§8.3's reservation transaction. Raises `CapacityError` on the
    first failed ceiling (transaction rolls back automatically — nothing
    partial is ever left behind). Statement timeout (§8.3: "5 s") is a
    deploy-time DB setting (`docker-compose.yml`/connection options),
    not something this function sets itself.
    """
    if not req.lines:
        raise CapacityError("validation_error", "An order needs at least one line.")
    if req.is_staff_assisted and req.created_by_user is None:
        # Order.created_by_user's own docstring: "Null for website
        # orders" — an assisted order needs a real actor, both for the
        # audit trail (order_events_staff_requires_actor_user's CHECK)
        # and because "assisted" without knowing who is meaningless.
        raise CapacityError(
            "validation_error", "An assisted order needs the staff user creating it."
        )

    now = req.now or now_sast()
    today = now.date()

    with transaction.atomic():
        try:
            trading_day = TradingDay.objects.select_for_update().get(date=req.trading_day_date)
        except TradingDay.DoesNotExist:
            raise CapacityError("day_closed", "That collection day isn't available.") from None

        check_day_open(trading_day)
        check_horizon(req.trading_day_date, today, settings.preorder_days)
        if req.is_staff_assisted:
            check_after_cutoff_permission(
                settings, req.trading_day_date, today, req.after_cutoff_reason
            )
        else:
            check_cutoff(req.trading_day_date, today, now.time(), trading_day.cutoff_time)

        try:
            slot = Slot.objects.select_for_update().get(pk=req.slot_id, trading_day=trading_day)
        except Slot.DoesNotExist:
            raise CapacityError(
                "slot_closed", "That collection slot doesn't exist for this day."
            ) from None
        check_slot_open(slot)

        check_day_cap(trading_day)
        check_slot_cap(slot)

        dish_ids = sorted({line.dish_id for line in req.lines})
        dishes = {d.pk: d for d in Dish.objects.select_for_update().filter(pk__in=dish_ids)}
        avail_rows = {
            a.dish_id: a
            for a in DayDishAvailability.objects.select_for_update()
            .filter(trading_day=trading_day, dish_id__in=dish_ids)
            .order_by("dish_id")
        }
        used_units = dish_units_used(trading_day, dish_ids)
        for idx, line in enumerate(req.lines):
            check_dish_line(
                dishes.get(line.dish_id), avail_rows.get(line.dish_id),
                used_units, line.dish_id, line.quantity, idx,
            )

        check_cash(trading_day, settings, today, req.payment_method)

        # --- ceilings passed: price snapshot, order number, insert (§11.6 step 2 / §8.3) ---
        option_value_ids = {vid for line in req.lines for vid in line.option_value_ids}
        option_value_qs = DishOptionValue.objects.select_related("option")
        option_values = {ov.pk: ov for ov in option_value_qs.filter(pk__in=option_value_ids)}

        seq = trading_day.next_order_seq
        trading_day.next_order_seq = seq + 1
        trading_day.save(update_fields=["next_order_seq"])
        order_number = format_order_number(trading_day.date, seq)

        line_specs = []
        subtotal_cents = 0
        for line in req.lines:
            dish = dishes[line.dish_id]
            values = [option_values[vid] for vid in line.option_value_ids if vid in option_values]
            pricing = price_line(
                dish.price_cents, [v.price_delta_cents for v in values], line.quantity
            )
            selections = [(v.option.name, v.name) for v in values]
            snapshot = [
                {"option": v.option.name, "value": v.name, "price_delta_cents": v.price_delta_cents}
                for v in values
            ]
            subtotal_cents += pricing.line_total_cents
            line_specs.append((dish, pricing, selections, snapshot, line.kitchen_note))

        if req.payment_method == PaymentMethod.EFT:
            status = "awaiting_eft"
            hold_expires_at = now + dt.timedelta(minutes=settings.eft_hold_minutes)
        else:
            status = "cash_request"
            hold_expires_at = None

        customer = _upsert_customer(req.customer_mobile_e164, req.customer_name, now)

        order = Order.objects.create(
            order_number=order_number,
            public_token=generate_public_token(),
            source=req.source,
            customer=customer,
            customer_name_snapshot=req.customer_name,
            customer_mobile_snapshot=req.customer_mobile_e164,
            note=req.note or None,
            trading_day=trading_day,
            slot=slot,
            status=status,
            payment_method=req.payment_method,
            subtotal_cents=subtotal_cents,
            discount_cents=0,
            total_cents=subtotal_cents,
            balance_due_cents=0,
            hold_expires_at=hold_expires_at,
            hold_extensions=0,
            created_by_user=req.created_by_user,
            after_cutoff_reason=req.after_cutoff_reason,
        )

        OrderLine.objects.bulk_create([
            OrderLine(
                order=order,
                dish=dish,
                dish_name_snapshot=dish.name,
                unit_price_cents_snapshot=pricing.unit_price_cents,
                quantity=pricing.quantity,
                options_snapshot=snapshot,
                option_key=derive_option_key(selections),
                line_total_cents=pricing.line_total_cents,
                kitchen_note=kitchen_note or None,
            )
            for dish, pricing, selections, snapshot, kitchen_note in line_specs
        ])

        PaymentModel.objects.create(
            order=order,
            method=req.payment_method,
            amount_cents=order.total_cents,
            reference=order_number,
            status=PaymentStatus.PENDING,
        )

        OrderEvent.objects.create(
            order=order,
            from_status=None,
            to_status=status,
            action="checkout",
            # Derived from whether there's an actual actor user, not from
            # `is_staff_assisted` alone (order_events_staff_requires_actor_user
            # — a STAFF-kind event with no actor_user violates that CHECK;
            # see the validation above, which is what actually guarantees
            # `req.created_by_user` is set whenever this branch is taken).
            actor_kind=ActorKind.STAFF if req.created_by_user else ActorKind.CUSTOMER,
            actor_user=req.created_by_user,
            payload={"source": req.source},
        )

        return order
