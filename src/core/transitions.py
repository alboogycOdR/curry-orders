"""The transitions engine (spec §9.1, §17.2: "`transitions.py` exposes
`apply(order, action, actor, payload, expected_status)`") — every §9.1
row except `checkout` (`core.capacity.reserve()`, milestone 3) and
`proof_uploaded`/`expire_hold` (`core.eft`, milestone 4, kept there
deliberately narrow rather than folded in here — see that module's own
docstring). Milestone 5's own scope line ("Transitions engine, audit,
EFT queue, stale_state handling") is what this module is for: the other
fifteen rows, one generic dispatcher, uniform `stale_state`/
`illegal_transition`/audit handling for all of them.

Only the EFT-queue-relevant actions (`verify_eft`, `reject_eft`,
`extend_hold`, `reinstate`, `expire_hold_now`) have a staff UI this pass
(`staff/views.py`'s payments queue, §12.3). The rest — kitchen/collection
board actions, cash accept/reject, `change_slot`, `amend_items` — are
implemented and tested here exactly like `core.capacity.reserve()` was
before milestone 3 had a view to call it: real, tested, unwired, waiting
for the milestone that builds their board (§22: kitchen/collection
board is milestone 6, cash path milestone 7, assisted create/calendar
milestone 9).

`core/` has no HTTP imports (§17.2) — `TransitionError` carries an
Appendix C error `code` (plus whatever extra fields it needs, e.g.
`current_status` for `stale_state`) rather than an HTTP response.

§8.6's concurrency rule applies uniformly here, not just to
`verify_eft`/`verify_eft` (the spec's own worked example): every
transition carries `expected_status`; a locked row whose status no
longer matches it is `409 stale_state` — checked *before* whether the
action is even legal for the actual current status, so a genuine race
(two staff, same order) is always reported as `stale_state`, and only a
same-status-but-wrong-action call (a client bug, not a race) is
`illegal_transition`.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass, field

from django.db import transaction

from .capacity import (
    OCCUPYING_STATUSES,
    CapacityError,
    check_day_cap,
    check_day_open,
    check_dish_line,
    check_slot_cap,
    check_slot_open,
    dish_units_used,
)
from .models import (
    ActorKind,
    CancellationReason,
    DayDishAvailability,
    Dish,
    DishOptionValue,
    Order,
    OrderEvent,
    OrderLine,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    Settings,
    Slot,
    TradingDay,
    User,
    UserRole,
)
from .ordering import LinePricing, derive_option_key, price_line
from .tz import SAST, now_sast

# §9.1's own footnote: "staff acting on the same order carries
# `collected_at <= 10 min`" for `uncollect` — a fixed rule, not a
# `Settings` field (nothing in §7.2's config table names it).
UNCOLLECT_WINDOW_MINUTES = 10


class TransitionError(Exception):
    def __init__(self, code: str, message: str, **extra: object) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra


@dataclass(frozen=True)
class Actor:
    kind: str  # ActorKind
    user: User | None = None


SYSTEM_ACTOR = Actor(kind=ActorKind.SYSTEM, user=None)


@dataclass
class AmendLine:
    """One line of an `amend_items` payload — same shape as
    `core.capacity.CheckoutLine`, kept separate so this module doesn't
    have to import a name whose docstring is checkout-specific."""

    dish_id: int
    quantity: int
    option_value_ids: list[int] = field(default_factory=list)
    kitchen_note: str = ""


# §9.1's "From" column, one entry per action. "Any non-terminal" is
# `OCCUPYING_STATUSES` exactly in this domain (§8.1: the occupying set
# *is* every status that isn't `payment_expired`/`cancelled`/`collected`).
_LEGAL_FROM: dict[str, frozenset[str]] = {
    "verify_eft": frozenset({OrderStatus.PAYMENT_REVIEW, OrderStatus.AWAITING_EFT}),
    "mark_payment_review": frozenset({OrderStatus.AWAITING_EFT}),
    "reject_eft": frozenset({OrderStatus.PAYMENT_REVIEW}),
    "extend_hold": frozenset({OrderStatus.AWAITING_EFT, OrderStatus.PAYMENT_REVIEW}),
    "expire_hold_now": frozenset({OrderStatus.AWAITING_EFT}),
    "reinstate": frozenset({OrderStatus.PAYMENT_EXPIRED}),
    "accept_cash": frozenset({OrderStatus.CASH_REQUEST}),
    "reject_cash": frozenset({OrderStatus.CASH_REQUEST}),
    "start_kitchen": frozenset({OrderStatus.CONFIRMED_PREP, OrderStatus.CASH_DUE}),
    "mark_ready": frozenset({OrderStatus.IN_KITCHEN}),
    "revert_ready": frozenset({OrderStatus.READY}),
    "mark_collected": frozenset({OrderStatus.READY}),
    "uncollect": frozenset({OrderStatus.COLLECTED}),
    "cancel": OCCUPYING_STATUSES,
    "close_out_no_show": frozenset({OrderStatus.READY}),
    "change_slot": OCCUPYING_STATUSES - {OrderStatus.READY},
    "amend_items": frozenset({
        OrderStatus.AWAITING_EFT, OrderStatus.PAYMENT_REVIEW, OrderStatus.CASH_REQUEST,
        OrderStatus.CONFIRMED_PREP, OrderStatus.CASH_DUE,
    }),
}


def _require_staff(actor: Actor) -> User:
    if actor.kind != ActorKind.STAFF or actor.user is None:
        raise TransitionError("validation_error", "This action needs a staff actor.")
    return actor.user


def _require_reason(reason: str | None) -> str:
    if not reason:
        raise TransitionError("reason_required", "A reason is required for this action.")
    return reason


# ---------------------------------------------------------------- EFT queue (§12.3)


def _do_verify_eft(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    from_status = order.status
    if from_status == OrderStatus.AWAITING_EFT:
        # §9.1: "*from awaiting_eft requires reason (e.g. seen in bank
        # app without proof)".
        _require_reason(reason)
    user = _require_staff(actor)

    payment = order.payment
    payment.status = PaymentStatus.VERIFIED
    payment.verified_by = user
    payment.verified_at = now
    payment.save(update_fields=["status", "verified_by", "verified_at"])

    order.status = OrderStatus.CONFIRMED_PREP
    order.confirmed_at = now
    order.hold_expires_at = None
    update_fields = ["status", "confirmed_at", "hold_expires_at", "updated_at"]
    order.save(update_fields=update_fields)

    event_payload: dict[str, object] = {}
    if order.trading_day.kitchen_locked_at is not None:
        event_payload["added_after_lock"] = True
    if reason:
        event_payload["reason"] = reason
    return event_payload


def _do_mark_payment_review(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    """§12.9's assisted-order "customer says they have paid" branch — no
    proof required (staff may separately attach one via the normal
    `core.eft.record_proof_upload` path if they have it). Unlike
    `proof_uploaded`, this never touches `payments.status`/
    `proof_uploaded_at` — there's no actual proof media yet, just the
    order moving into the same review queue a real upload would land it
    in (`staff/views.py::payments_queue` already shows both
    `awaiting_eft` and `payment_review`).
    """
    _require_staff(actor)
    order.status = OrderStatus.PAYMENT_REVIEW
    order.save(update_fields=["status", "updated_at"])
    return {}


def _do_reject_eft(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    reason = _require_reason(reason)
    _require_staff(actor)

    payment = order.payment
    payment.status = PaymentStatus.PENDING
    payment.rejected_reason = reason
    payment.save(update_fields=["status", "rejected_reason"])
    # Current proof stays linked for audit (§9.1); hold is unchanged —
    # staff may separately `extend_hold`.

    order.status = OrderStatus.AWAITING_EFT
    order.save(update_fields=["status", "updated_at"])
    return {}


def _do_extend_hold(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    _require_staff(actor)
    settings = Settings.current()
    if order.hold_extensions >= settings.max_hold_extensions:
        raise TransitionError(
            "validation_error", "This order's hold has already been extended the maximum times.",
        )
    order.hold_expires_at = (order.hold_expires_at or now) + dt.timedelta(
        minutes=settings.hold_extension_minutes
    )
    order.hold_extensions += 1
    order.save(update_fields=["hold_expires_at", "hold_extensions", "updated_at"])
    return {"hold_expires_at": order.hold_expires_at.isoformat()}


def _do_expire_hold_now(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    # Staff's "Expire now" (§12.3) — unlike the `expire_holds` job
    # (core.eft), no `hold_expires_at < now` guard: staff can force it
    # any time the order is still `awaiting_eft`.
    _require_staff(actor)
    order.status = OrderStatus.PAYMENT_EXPIRED
    order.save(update_fields=["status", "updated_at"])

    payment = order.payment
    payment.status = PaymentStatus.EXPIRED
    payment.save(update_fields=["status"])
    return {}


def _do_reinstate(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    reason = _require_reason(reason)
    _require_staff(actor)
    settings = Settings.current()

    trading_day = TradingDay.objects.select_for_update().get(pk=order.trading_day_id)
    check_day_open(trading_day)  # "day must be open" — cutoff explicitly ignored (§9.1)

    slot = Slot.objects.select_for_update().get(pk=order.slot_id)
    check_slot_open(slot)
    check_day_cap(trading_day)
    check_slot_cap(slot)

    dish_ids = sorted({line.dish_id for line in order.lines.all() if line.dish_id is not None})
    if dish_ids:
        avail_rows = {
            a.dish_id: a
            for a in DayDishAvailability.objects.select_for_update()
            .filter(trading_day=trading_day, dish_id__in=dish_ids)
            .order_by("dish_id")
        }
        dishes = {d.pk: d for d in Dish.objects.select_for_update().filter(pk__in=dish_ids)}
        used_units = dish_units_used(trading_day, dish_ids, exclude_order_id=order.pk)
        for idx, line in enumerate(order.lines.all()):
            if line.dish_id is None:
                continue
            check_dish_line(
                dishes.get(line.dish_id), avail_rows.get(line.dish_id),
                used_units, line.dish_id, line.quantity, idx,
            )

    order.status = OrderStatus.AWAITING_EFT
    order.hold_expires_at = now + dt.timedelta(minutes=settings.eft_hold_minutes)
    order.hold_extensions = 0
    order.save(update_fields=["status", "hold_expires_at", "hold_extensions", "updated_at"])

    payment = order.payment
    payment.status = PaymentStatus.PENDING
    payment.save(update_fields=["status"])
    return {"reason": reason}


# ---------------------------------------------------------------- cash (§9.1, milestone 7's board)


def _do_accept_cash(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    _require_staff(actor)
    order.status = OrderStatus.CASH_DUE
    order.confirmed_at = now
    order.save(update_fields=["status", "confirmed_at", "updated_at"])
    return {}


def _do_reject_cash(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    _require_staff(actor)
    order.status = OrderStatus.CANCELLED
    order.cancellation_reason = CancellationReason.CASH_REJECTED
    order.cancellation_note = reason or None
    order.cancelled_at = now
    order.save(update_fields=[
        "status", "cancellation_reason", "cancellation_note", "cancelled_at", "updated_at",
    ])

    payment = order.payment
    payment.status = PaymentStatus.CANCELLED
    payment.save(update_fields=["status"])
    return {}


# ---------------------------------------------------------------- kitchen board (§9.1, M6's board)


def _do_start_kitchen(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    _require_staff(actor)
    order.status = OrderStatus.IN_KITCHEN
    order.in_kitchen_at = now
    order.dish_units_consumed = True
    order.save(update_fields=["status", "in_kitchen_at", "dish_units_consumed", "updated_at"])
    return {}


def _do_mark_ready(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    # §13: "optional SMS if sms_enabled" — no notifications/ implementation
    # this pass (see that app's own placeholder); a failure to send would
    # never block this transition anyway, so its absence changes nothing
    # here.
    _require_staff(actor)
    order.status = OrderStatus.READY
    order.ready_at = now
    order.save(update_fields=["status", "ready_at", "updated_at"])
    return {}


def _do_revert_ready(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    _require_staff(actor)
    order.status = OrderStatus.IN_KITCHEN
    order.ready_at = None
    order.save(update_fields=["status", "ready_at", "updated_at"])
    return {"reason": reason} if reason else {}


# ---------------------------------------------------------------- collection board (§9.1, M6)


def _do_mark_collected(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    _require_staff(actor)
    order.status = OrderStatus.COLLECTED
    order.collected_at = now
    order.save(update_fields=["status", "collected_at", "updated_at"])

    event_payload: dict[str, object] = {}
    if order.payment_method == PaymentMethod.CASH:
        amount = payload.get("cash_amount_received_cents", order.total_cents)
        if not isinstance(amount, int) or amount < 0:
            raise TransitionError(
                "validation_error", "cash_amount_received_cents must be a non-negative integer.",
            )
        payment = order.payment
        payment.status = PaymentStatus.COLLECTED_CASH
        payment.cash_received_by = actor.user
        payment.cash_received_at = now
        payment.cash_amount_received_cents = amount
        payment.save(update_fields=[
            "status", "cash_received_by", "cash_received_at", "cash_amount_received_cents",
        ])
        event_payload["cash_amount_received_cents"] = amount
    # EFT: payment is already `verified` from `verify_eft` — unchanged here.
    return event_payload


def _do_uncollect(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    reason = _require_reason(reason)
    _require_staff(actor)
    if order.collected_at is None or now - order.collected_at > dt.timedelta(
        minutes=UNCOLLECT_WINDOW_MINUTES
    ):
        raise TransitionError(
            "illegal_transition",
            f"Can only uncollect within {UNCOLLECT_WINDOW_MINUTES} minutes of collection.",
        )

    event_payload: dict[str, object] = {"reason": reason}
    payment = order.payment
    was_cash_collected = (
        order.payment_method == PaymentMethod.CASH
        and payment.status == PaymentStatus.COLLECTED_CASH
    )
    if was_cash_collected:
        # "cash receipt row retained in event payload and cleared on
        # payment" (§9.1) — the audit trail keeps the figures, the live
        # `payments` row goes back to awaiting collection.
        event_payload["cleared_cash_receipt"] = {
            "cash_received_by": payment.cash_received_by_id,
            "cash_received_at": payment.cash_received_at.isoformat()
            if payment.cash_received_at else None,
            "cash_amount_received_cents": payment.cash_amount_received_cents,
        }
        payment.status = PaymentStatus.PENDING
        payment.cash_received_by = None
        payment.cash_received_at = None
        payment.cash_amount_received_cents = None
        payment.save(update_fields=[
            "status", "cash_received_by", "cash_received_at", "cash_amount_received_cents",
        ])

    order.status = OrderStatus.READY
    order.collected_at = None
    order.save(update_fields=["status", "collected_at", "updated_at"])
    return event_payload


def _do_close_out_no_show(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    settings = Settings.current()
    trading_day = order.trading_day
    deadline = dt.datetime.combine(
        trading_day.date, trading_day.window_end, tzinfo=SAST
    ) + dt.timedelta(minutes=settings.collection_grace_minutes)
    if now < deadline:
        raise TransitionError(
            "illegal_transition", "The collection window plus grace period hasn't passed yet.",
        )
    order.status = OrderStatus.CANCELLED
    order.cancellation_reason = CancellationReason.NO_SHOW
    order.cancelled_at = now
    # "Dish units stay consumed; payments.status unchanged" (§9.1) —
    # deliberately not touching `dish_units_consumed` or `payment.status`.
    order.save(update_fields=["status", "cancellation_reason", "cancelled_at", "updated_at"])
    return {}


# ---------------------------------------------------------------- cancel, any board


def _do_cancel(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    user = _require_staff(actor)
    from_status = order.status
    if from_status in (OrderStatus.IN_KITCHEN, OrderStatus.READY) and user.role != UserRole.OWNER:
        raise TransitionError("owner_only", "Only the owner can cancel from this stage.")

    cancellation_reason = payload.get("cancellation_reason")
    if cancellation_reason not in CancellationReason.values:
        raise TransitionError(
            "validation_error", "A valid cancellation_reason is required.",
        )

    order.status = OrderStatus.CANCELLED
    order.cancellation_reason = cancellation_reason
    order.cancellation_note = reason or None
    order.cancelled_at = now
    if order.payment.status == PaymentStatus.VERIFIED:
        # "if EFT verified, set refund_note = 'refund_pending'" (§9.1) —
        # the actual refund happens off-platform; this is just the flag.
        order.refund_note = "refund_pending"
        update_fields = [
            "status", "cancellation_reason", "cancellation_note", "cancelled_at",
            "refund_note", "updated_at",
        ]
    else:
        update_fields = [
            "status", "cancellation_reason", "cancellation_note", "cancelled_at", "updated_at",
        ]
    order.save(update_fields=update_fields)
    # "Release day/slot/cash" is automatic — capacity is always computed
    # live from OCCUPYING_STATUSES membership (core.capacity), never a
    # counter to decrement. "Release dish units only if
    # dish_units_consumed = false" is equally automatic: dish_units_used()
    # only still counts a cancelled order's lines when that flag is true.
    return {}


# ---------------------------------------------------------------- change_slot / amend_items


def _do_change_slot(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    _require_staff(actor)
    new_slot_id = payload.get("new_slot_id")
    if not isinstance(new_slot_id, int):
        raise TransitionError("validation_error", "new_slot_id is required.")

    try:
        new_slot = Slot.objects.select_for_update().get(
            pk=new_slot_id, trading_day_id=order.trading_day_id,
        )
    except Slot.DoesNotExist:
        raise TransitionError(
            "slot_closed", "That collection slot doesn't exist for this day.",
        ) from None
    check_slot_open(new_slot)
    check_slot_cap(new_slot)

    old_slot_id = order.slot_id
    order.slot = new_slot
    order.save(update_fields=["slot", "updated_at"])
    return {"from_slot": old_slot_id, "to_slot": new_slot_id}


def _do_amend_items(
    order: Order, actor: Actor, reason: str | None, now: dt.datetime, payload: dict[str, object],
) -> dict[str, object]:
    reason = _require_reason(reason)
    _require_staff(actor)
    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list) or not raw_lines:
        raise TransitionError("validation_error", "An order needs at least one line.")
    amend_lines: list[AmendLine] = [
        raw if isinstance(raw, AmendLine) else AmendLine(**raw) for raw in raw_lines
    ]

    trading_day = TradingDay.objects.select_for_update().get(pk=order.trading_day_id)

    old_qty_by_dish: dict[int, int] = {}
    for order_line in order.lines.all():
        if order_line.dish_id is not None:
            old_qty_by_dish[order_line.dish_id] = (
                old_qty_by_dish.get(order_line.dish_id, 0) + order_line.quantity
            )
    new_qty_by_dish: dict[int, int] = {}
    for amend_line in amend_lines:
        new_qty_by_dish[amend_line.dish_id] = (
            new_qty_by_dish.get(amend_line.dish_id, 0) + amend_line.quantity
        )

    dish_ids = sorted(set(new_qty_by_dish))
    dishes = {d.pk: d for d in Dish.objects.select_for_update().filter(pk__in=dish_ids)}
    avail_rows = {
        a.dish_id: a
        for a in DayDishAvailability.objects.select_for_update()
        .filter(trading_day=trading_day, dish_id__in=dish_ids)
        .order_by("dish_id")
    }
    # "dish ceilings rechecked for increased units" (§9.1) — only where
    # this order's own new total for a dish exceeds what it already held;
    # a same-or-decreased quantity never needs a recheck, and this
    # order's own prior lines are excluded from `used_units` so they
    # don't count against themselves.
    used_units = dish_units_used(trading_day, dish_ids, exclude_order_id=order.pk)
    for idx, dish_id in enumerate(dish_ids):
        new_qty = new_qty_by_dish[dish_id]
        if new_qty <= old_qty_by_dish.get(dish_id, 0):
            continue
        check_dish_line(
            dishes.get(dish_id), avail_rows.get(dish_id), used_units, dish_id, new_qty, idx,
        )

    option_value_ids = {vid for al in amend_lines for vid in al.option_value_ids}
    option_values = {
        ov.pk: ov
        for ov in DishOptionValue.objects.select_related("option").filter(pk__in=option_value_ids)
    }

    new_subtotal_cents = 0
    line_specs: list[
        tuple[Dish, LinePricing, list[tuple[str, str]], list[dict[str, object]], str]
    ] = []
    for amend_line in amend_lines:
        dish = dishes.get(amend_line.dish_id)
        if dish is None:
            raise TransitionError(
                "validation_error", f"Unknown dish {amend_line.dish_id!r}.",
            )
        values = [
            option_values[vid] for vid in amend_line.option_value_ids if vid in option_values
        ]
        pricing = price_line(
            dish.price_cents, [v.price_delta_cents for v in values], amend_line.quantity
        )
        selections = [(v.option.name, v.name) for v in values]
        snapshot = [
            {"option": v.option.name, "value": v.name, "price_delta_cents": v.price_delta_cents}
            for v in values
        ]
        new_subtotal_cents += pricing.line_total_cents
        line_specs.append((dish, pricing, selections, snapshot, amend_line.kitchen_note))

    old_total_cents = order.total_cents
    order.lines.all().delete()
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

    order.subtotal_cents = new_subtotal_cents
    order.total_cents = new_subtotal_cents - order.discount_cents
    update_fields = ["subtotal_cents", "total_cents", "updated_at"]
    if order.payment.status == PaymentStatus.VERIFIED:
        if order.total_cents > old_total_cents:
            order.balance_due_cents = order.total_cents - old_total_cents
            update_fields.append("balance_due_cents")
        elif order.total_cents < old_total_cents:
            order.refund_note = "refund_pending"
            update_fields.append("refund_note")
    order.save(update_fields=update_fields)
    return {
        "reason": reason, "old_total_cents": old_total_cents, "new_total_cents": order.total_cents,
    }


_Handler = Callable[[Order, Actor, "str | None", dt.datetime, dict[str, object]], dict[str, object]]

_HANDLERS: dict[str, _Handler] = {
    "verify_eft": _do_verify_eft,
    "mark_payment_review": _do_mark_payment_review,
    "reject_eft": _do_reject_eft,
    "extend_hold": _do_extend_hold,
    "expire_hold_now": _do_expire_hold_now,
    "reinstate": _do_reinstate,
    "accept_cash": _do_accept_cash,
    "reject_cash": _do_reject_cash,
    "start_kitchen": _do_start_kitchen,
    "mark_ready": _do_mark_ready,
    "revert_ready": _do_revert_ready,
    "mark_collected": _do_mark_collected,
    "uncollect": _do_uncollect,
    "close_out_no_show": _do_close_out_no_show,
    "cancel": _do_cancel,
    "change_slot": _do_change_slot,
    "amend_items": _do_amend_items,
}


def apply(
    order: Order,
    action: str,
    actor: Actor,
    expected_status: str,
    *,
    reason: str | None = None,
    payload: dict[str, object] | None = None,
    now: dt.datetime | None = None,
) -> Order:
    """§17.2's `apply(order, action, actor, payload, expected_status)`.
    Locks the order row, checks `expected_status` (§8.6: `stale_state`
    before `illegal_transition` — see this module's own docstring for
    why that order matters), dispatches to the action's handler, writes
    one `order_events` row, returns the updated `Order`.
    """
    handler = _HANDLERS.get(action)
    if handler is None:
        raise TransitionError("illegal_transition", f"Unknown action {action!r}.")

    now = now or now_sast()
    payload = payload or {}

    with transaction.atomic():
        locked = (
            Order.objects.select_for_update(of=("self",))
            .select_related("payment", "trading_day")
            .get(pk=order.pk)
        )
        if locked.status != expected_status:
            raise TransitionError(
                "stale_state", "This order has changed since you last saw it.",
                current_status=locked.status,
            )
        if locked.status not in _LEGAL_FROM[action]:
            raise TransitionError(
                "illegal_transition", f"{action!r} isn't legal from {locked.status!r}.",
            )

        from_status = locked.status
        try:
            event_payload = handler(locked, actor, reason, now, payload)
        except CapacityError as exc:
            # reinstate/change_slot/amend_items reuse core.capacity's own
            # ceiling checks — surface the same Appendix C code rather
            # than translating it into a transitions-specific one.
            raise TransitionError(
                exc.code, exc.message,
                line_index=exc.line_index, alternatives=exc.alternatives or None,
            ) from exc

        OrderEvent.objects.create(
            order=locked,
            from_status=from_status,
            to_status=locked.status,
            action=action,
            actor_kind=actor.kind,
            actor_user=actor.user,
            payload=event_payload,
        )
    locked.refresh_from_db()
    return locked


def close_out_day(trading_day: TradingDay, actor: Actor, *, now: dt.datetime | None = None) -> int:
    """§12.5's "Close out day" button and §17.1's nightly `close_out_days`
    job (23:30 SAST) are the same operation with a different actor: every
    order still `ready` for this trading day -> `no_show` (one
    `close_out_no_show` `apply()` call each, so each gets its own
    transaction/lock/audit row, not one giant one), then `closed_out_at`
    set if it isn't already. A no-op (returns 0, touches nothing) before
    the grace deadline — safe to call from a job or a button with no
    external gating required, though `staff/views.py`'s button still
    only renders once the deadline has passed (§12.5: "visible after
    grace").
    """
    now = now or now_sast()
    settings = Settings.current()
    deadline = dt.datetime.combine(
        trading_day.date, trading_day.window_end, tzinfo=SAST
    ) + dt.timedelta(minutes=settings.collection_grace_minutes)
    if now < deadline:
        return 0

    order_ids = list(
        Order.objects.filter(trading_day=trading_day, status=OrderStatus.READY)
        .values_list("pk", flat=True)
    )
    closed = 0
    for order_id in order_ids:
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            continue
        try:
            apply(order, "close_out_no_show", actor, OrderStatus.READY, now=now)
            closed += 1
        except TransitionError:
            continue  # e.g. a concurrent staff action already moved it on

    if trading_day.closed_out_at is None:
        trading_day.closed_out_at = now
        trading_day.closed_out_by = actor.user
        trading_day.save(update_fields=["closed_out_at", "closed_out_by"])
    return closed
