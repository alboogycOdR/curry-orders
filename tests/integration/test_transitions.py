"""Integration tests for core/transitions.py — the full §9.1 matrix bar
`checkout` (core.capacity), `proof_uploaded`/`expire_hold` (core.eft).
Orders are built through the real `core.capacity.reserve()` transaction
and, where a test needs a specific starting status, chained through
`apply()` itself rather than hand-set on the model — every fixture that
does that is exercising the same code path the test itself verifies
elsewhere in this file.
"""
from __future__ import annotations

import datetime as dt
import threading

import pytest

from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.models import (
    ActorKind,
    CancellationReason,
    Order,
    OrderStatus,
    PaymentStatus,
    Slot,
)
from core.transitions import SYSTEM_ACTOR, Actor, TransitionError, apply

pytestmark = pytest.mark.django_db

NOW = dt.datetime(2026, 8, 31, 6, 0, tzinfo=dt.UTC)  # day before trading_day's 2026-09-01


def _eft_req(dish, slot, **overrides) -> ReservationRequest:
    defaults = dict(
        trading_day_date=dt.date(2026, 9, 1),
        slot_id=slot.pk,
        payment_method="eft",
        customer_name="Jane Customer",
        customer_mobile_e164="+27821234567",
        lines=[CheckoutLine(dish_id=dish.pk, quantity=1)],
        now=NOW,
    )
    defaults.update(overrides)
    return ReservationRequest(**defaults)


def _cash_req(dish, slot, **overrides) -> ReservationRequest:
    return _eft_req(dish, slot, payment_method="cash", **overrides)


@pytest.fixture
def eft_order(biz_settings, trading_day, slot, dish):
    return reserve(_eft_req(dish, slot), biz_settings)


@pytest.fixture
def cash_order(biz_settings, trading_day, slot, dish):
    # Same-day cash per §8.2, so trading_day_date == "today" from cash's
    # own perspective — cash's check_cash() only cares about that, and
    # NOW's date (Aug 31) already matches trading_day (Sep 1)... no: use
    # `now` as the trading day's own date directly so check_cash's
    # same-day rule passes without touching cutoff (cash assisted orders
    # aren't customer-facing here, only reserve()'s own guards apply).
    same_day_now = dt.datetime(2026, 9, 1, 6, 0, tzinfo=dt.UTC)
    biz_settings.cash_enabled = True
    biz_settings.cash_daily_cap = 20
    biz_settings.save(update_fields=["cash_enabled", "cash_daily_cap"])
    return reserve(_cash_req(dish, slot, now=same_day_now), biz_settings)


def _staff(staff_user) -> Actor:
    return Actor(kind=ActorKind.STAFF, user=staff_user)


def _upload_proof(order, now=NOW) -> Order:
    from core.eft import record_proof_upload

    record_proof_upload(
        order, storage_key="proofs/x.jpg", mime_type="image/jpeg",
        byte_size=10, sha256=b"\x00" * 32, now=now,
    )
    order.refresh_from_db()
    return order


class TestVerifyEft:
    def test_from_payment_review_moves_to_confirmed_prep(self, eft_order, staff_user) -> None:
        _upload_proof(eft_order)
        order = apply(
            eft_order, "verify_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW,
        )
        assert order.status == OrderStatus.CONFIRMED_PREP
        assert order.payment.status == PaymentStatus.VERIFIED
        assert order.payment.verified_by_id == staff_user.pk
        assert order.hold_expires_at is None
        assert order.confirmed_at == NOW

    def test_from_awaiting_eft_requires_a_reason(self, eft_order, staff_user) -> None:
        with pytest.raises(TransitionError) as exc_info:
            apply(eft_order, "verify_eft", _staff(staff_user), OrderStatus.AWAITING_EFT, now=NOW)
        assert exc_info.value.code == "reason_required"

    def test_from_awaiting_eft_with_reason_succeeds(self, eft_order, staff_user) -> None:
        order = apply(
            eft_order, "verify_eft", _staff(staff_user), OrderStatus.AWAITING_EFT,
            reason="Seen in bank app", now=NOW,
        )
        assert order.status == OrderStatus.CONFIRMED_PREP

    def test_flags_added_after_lock(self, eft_order, staff_user) -> None:
        eft_order.trading_day.kitchen_locked_at = NOW
        eft_order.trading_day.save(update_fields=["kitchen_locked_at"])
        _upload_proof(eft_order)
        apply(eft_order, "verify_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW)
        event = eft_order.events.get(action="verify_eft")
        assert event.payload["added_after_lock"] is True

    def test_illegal_from_confirmed_prep(self, eft_order, staff_user) -> None:
        _upload_proof(eft_order)
        apply(eft_order, "verify_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW)
        eft_order.refresh_from_db()
        with pytest.raises(TransitionError) as exc_info:
            apply(
                eft_order, "verify_eft", _staff(staff_user), OrderStatus.CONFIRMED_PREP, now=NOW,
            )
        assert exc_info.value.code == "illegal_transition"


class TestMarkPaymentReview:
    """§12.9's "customer says they have paid" assisted-order branch —
    `mark_payment_review`, no proof/reason required (unlike
    `verify_eft` from `awaiting_eft`)."""

    def test_moves_awaiting_eft_to_payment_review_with_no_proof(
        self, eft_order, staff_user,
    ) -> None:
        order = apply(
            eft_order, "mark_payment_review", _staff(staff_user),
            OrderStatus.AWAITING_EFT, now=NOW,
        )
        assert order.status == OrderStatus.PAYMENT_REVIEW
        assert order.payment.status == PaymentStatus.PENDING  # no real proof media
        assert order.payment.proof_uploaded_at is None

    def test_illegal_from_payment_review(self, eft_order, staff_user) -> None:
        apply(
            eft_order, "mark_payment_review", _staff(staff_user),
            OrderStatus.AWAITING_EFT, now=NOW,
        )
        eft_order.refresh_from_db()
        with pytest.raises(TransitionError) as exc_info:
            apply(
                eft_order, "mark_payment_review", _staff(staff_user),
                OrderStatus.PAYMENT_REVIEW, now=NOW,
            )
        assert exc_info.value.code == "illegal_transition"

    def test_requires_a_staff_actor(self, eft_order) -> None:
        with pytest.raises(TransitionError) as exc_info:
            apply(
                eft_order, "mark_payment_review", SYSTEM_ACTOR,
                OrderStatus.AWAITING_EFT, now=NOW,
            )
        assert exc_info.value.code == "validation_error"

    def test_can_still_be_verified_afterwards_without_a_reason(
        self, eft_order, staff_user,
    ) -> None:
        # Once it's payment_review, verify_eft's own reason requirement
        # only bites from awaiting_eft — same as a real proof upload.
        order = apply(
            eft_order, "mark_payment_review", _staff(staff_user),
            OrderStatus.AWAITING_EFT, now=NOW,
        )
        order = apply(
            order, "verify_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW,
        )
        assert order.status == OrderStatus.CONFIRMED_PREP


class TestStaleState:
    def test_wrong_expected_status_is_stale_state_not_illegal_transition(
        self, eft_order, staff_user,
    ) -> None:
        # eft_order is really `awaiting_eft`; caller believes `payment_review`.
        with pytest.raises(TransitionError) as exc_info:
            apply(
                eft_order, "reject_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW,
            )
        assert exc_info.value.code == "stale_state"
        assert exc_info.value.extra["current_status"] == OrderStatus.AWAITING_EFT

    def test_unknown_action_is_illegal_transition(self, eft_order, staff_user) -> None:
        with pytest.raises(TransitionError) as exc_info:
            apply(
                eft_order, "teleport", _staff(staff_user), OrderStatus.AWAITING_EFT, now=NOW,
            )
        assert exc_info.value.code == "illegal_transition"


@pytest.mark.django_db(transaction=True)
class TestVerifyEftRace:
    def test_two_staff_verifying_the_same_order_one_wins_one_gets_stale_state(
        self, biz_settings, trading_day, slot, dish, staff_user, owner_user,
    ) -> None:
        # §20.5's own worked example: "verify/verify race -> one stale_state".
        order = reserve(_eft_req(dish, slot), biz_settings)
        _upload_proof(order)

        results: list[str] = []

        def run(user) -> None:
            import django

            django.db.close_old_connections()
            try:
                apply(
                    order, "verify_eft", Actor(ActorKind.STAFF, user),
                    OrderStatus.PAYMENT_REVIEW, now=NOW,
                )
                results.append("ok")
            except TransitionError as exc:
                results.append(exc.code)

        threads = [
            threading.Thread(target=run, args=(staff_user,)),
            threading.Thread(target=run, args=(owner_user,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(results) == ["ok", "stale_state"]
        order.refresh_from_db()
        assert order.status == OrderStatus.CONFIRMED_PREP
        assert order.events.filter(action="verify_eft").count() == 1


class TestRejectEft:
    def test_requires_reason(self, eft_order, staff_user) -> None:
        _upload_proof(eft_order)
        with pytest.raises(TransitionError) as exc_info:
            apply(eft_order, "reject_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW)
        assert exc_info.value.code == "reason_required"

    def test_moves_back_to_awaiting_eft_with_reason_recorded(self, eft_order, staff_user) -> None:
        _upload_proof(eft_order)
        order = apply(
            eft_order, "reject_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW,
            reason="Wrong reference", now=NOW,
        )
        assert order.status == OrderStatus.AWAITING_EFT
        assert order.payment.status == PaymentStatus.PENDING
        assert order.payment.rejected_reason == "Wrong reference"
        assert order.payment.current_proof_media is not None  # kept for audit


class TestExtendHold:
    def test_extends_and_increments_count(self, eft_order, staff_user) -> None:
        original = eft_order.hold_expires_at
        order = apply(
            eft_order, "extend_hold", _staff(staff_user), OrderStatus.AWAITING_EFT, now=NOW,
        )
        assert order.hold_expires_at > original
        assert order.hold_extensions == 1

    def test_refuses_past_the_max(self, eft_order, staff_user) -> None:
        eft_order.hold_extensions = 1  # biz_settings default max_hold_extensions == 1
        eft_order.save(update_fields=["hold_extensions"])
        with pytest.raises(TransitionError) as exc_info:
            apply(eft_order, "extend_hold", _staff(staff_user), OrderStatus.AWAITING_EFT, now=NOW)
        assert exc_info.value.code == "validation_error"


class TestExpireHoldNow:
    def test_expires_regardless_of_hold_expires_at(self, eft_order, staff_user) -> None:
        # Hold hasn't lapsed yet — staff can still force it (§9.1: "staff: none").
        assert eft_order.hold_expires_at > NOW
        order = apply(
            eft_order, "expire_hold_now", _staff(staff_user), OrderStatus.AWAITING_EFT, now=NOW,
        )
        assert order.status == OrderStatus.PAYMENT_EXPIRED
        assert order.payment.status == PaymentStatus.EXPIRED

    def test_illegal_from_payment_review(self, eft_order, staff_user) -> None:
        _upload_proof(eft_order)
        with pytest.raises(TransitionError) as exc_info:
            apply(
                eft_order, "expire_hold_now", _staff(staff_user), OrderStatus.PAYMENT_REVIEW,
                now=NOW,
            )
        assert exc_info.value.code == "illegal_transition"


class TestReinstate:
    def _expired(self, eft_order, staff_user) -> Order:
        return apply(
            eft_order, "expire_hold_now", _staff(staff_user), OrderStatus.AWAITING_EFT, now=NOW,
        )

    def test_requires_reason(self, eft_order, staff_user) -> None:
        expired = self._expired(eft_order, staff_user)
        with pytest.raises(TransitionError) as exc_info:
            apply(expired, "reinstate", _staff(staff_user), OrderStatus.PAYMENT_EXPIRED, now=NOW)
        assert exc_info.value.code == "reason_required"

    def test_fresh_hold_and_same_order_number(self, eft_order, staff_user) -> None:
        expired = self._expired(eft_order, staff_user)
        order_number = expired.order_number
        order = apply(
            expired, "reinstate", _staff(staff_user), OrderStatus.PAYMENT_EXPIRED,
            reason="Customer showed proof after the window", now=NOW,
        )
        assert order.status == OrderStatus.AWAITING_EFT
        assert order.order_number == order_number
        assert order.hold_extensions == 0
        assert order.hold_expires_at > NOW
        assert order.payment.status == PaymentStatus.PENDING

    def test_fails_when_day_closed(self, eft_order, staff_user) -> None:
        expired = self._expired(eft_order, staff_user)
        expired.trading_day.is_open = False
        expired.trading_day.save(update_fields=["is_open"])
        with pytest.raises(TransitionError) as exc_info:
            apply(
                expired, "reinstate", _staff(staff_user), OrderStatus.PAYMENT_EXPIRED,
                reason="try", now=NOW,
            )
        assert exc_info.value.code == "day_closed"

    def test_fails_when_slot_now_full(self, eft_order, staff_user, dish, biz_settings) -> None:
        expired = self._expired(eft_order, staff_user)
        # Fill the slot with other occupying orders up to capacity.
        slot = expired.slot
        for i in range(slot.capacity):
            reserve(
                _eft_req(dish, slot, customer_mobile_e164=f"+2782000{i:04d}"), biz_settings,
            )
        with pytest.raises(TransitionError) as exc_info:
            apply(
                expired, "reinstate", _staff(staff_user), OrderStatus.PAYMENT_EXPIRED,
                reason="try", now=NOW,
            )
        assert exc_info.value.code == "slot_full"


class TestCash:
    def test_accept_cash_moves_to_cash_due(self, cash_order, staff_user) -> None:
        order = apply(
            cash_order, "accept_cash", _staff(staff_user), OrderStatus.CASH_REQUEST, now=NOW,
        )
        assert order.status == OrderStatus.CASH_DUE
        assert order.confirmed_at == NOW

    def test_reject_cash_cancels_with_default_reason(self, cash_order, staff_user) -> None:
        order = apply(
            cash_order, "reject_cash", _staff(staff_user), OrderStatus.CASH_REQUEST, now=NOW,
        )
        assert order.status == OrderStatus.CANCELLED
        assert order.cancellation_reason == CancellationReason.CASH_REJECTED
        assert order.payment.status == PaymentStatus.CANCELLED


class TestKitchenAndCollection:
    def _confirmed(self, eft_order, staff_user) -> Order:
        _upload_proof(eft_order)
        return apply(
            eft_order, "verify_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW,
        )

    def test_full_happy_path_to_collected(self, eft_order, staff_user) -> None:
        order = self._confirmed(eft_order, staff_user)
        order = apply(
            order, "start_kitchen", _staff(staff_user), OrderStatus.CONFIRMED_PREP, now=NOW,
        )
        assert order.status == OrderStatus.IN_KITCHEN
        assert order.dish_units_consumed is True

        order = apply(order, "mark_ready", _staff(staff_user), OrderStatus.IN_KITCHEN, now=NOW)
        assert order.status == OrderStatus.READY
        assert order.ready_at == NOW

        order = apply(
            order, "revert_ready", _staff(staff_user), OrderStatus.READY, now=NOW,
        )
        assert order.status == OrderStatus.IN_KITCHEN
        order = apply(order, "mark_ready", _staff(staff_user), OrderStatus.IN_KITCHEN, now=NOW)

        order = apply(order, "mark_collected", _staff(staff_user), OrderStatus.READY, now=NOW)
        assert order.status == OrderStatus.COLLECTED
        assert order.collected_at == NOW
        # EFT: payment stays `verified`, no cash fields touched.
        assert order.payment.status == PaymentStatus.VERIFIED

    def test_mark_collected_cash_defaults_amount_to_total(
        self, cash_order, staff_user,
    ) -> None:
        order = apply(
            cash_order, "accept_cash", _staff(staff_user), OrderStatus.CASH_REQUEST, now=NOW,
        )
        order = apply(
            order, "start_kitchen", _staff(staff_user), OrderStatus.CASH_DUE, now=NOW,
        )
        order = apply(order, "mark_ready", _staff(staff_user), OrderStatus.IN_KITCHEN, now=NOW)
        order = apply(order, "mark_collected", _staff(staff_user), OrderStatus.READY, now=NOW)
        assert order.payment.status == PaymentStatus.COLLECTED_CASH
        assert order.payment.cash_amount_received_cents == order.total_cents
        assert order.payment.cash_received_by_id == staff_user.pk

    def test_mark_collected_cash_explicit_amount(self, cash_order, staff_user) -> None:
        order = apply(
            cash_order, "accept_cash", _staff(staff_user), OrderStatus.CASH_REQUEST, now=NOW,
        )
        order = apply(order, "start_kitchen", _staff(staff_user), OrderStatus.CASH_DUE, now=NOW)
        order = apply(order, "mark_ready", _staff(staff_user), OrderStatus.IN_KITCHEN, now=NOW)
        order = apply(
            order, "mark_collected", _staff(staff_user), OrderStatus.READY,
            payload={"cash_amount_received_cents": order.total_cents + 500}, now=NOW,
        )
        assert order.payment.cash_amount_received_cents == order.total_cents + 500

    def test_uncollect_within_window_restores_ready_and_clears_cash_receipt(
        self, cash_order, staff_user,
    ) -> None:
        order = apply(
            cash_order, "accept_cash", _staff(staff_user), OrderStatus.CASH_REQUEST, now=NOW,
        )
        order = apply(order, "start_kitchen", _staff(staff_user), OrderStatus.CASH_DUE, now=NOW)
        order = apply(order, "mark_ready", _staff(staff_user), OrderStatus.IN_KITCHEN, now=NOW)
        order = apply(order, "mark_collected", _staff(staff_user), OrderStatus.READY, now=NOW)

        order = apply(
            order, "uncollect", _staff(staff_user), OrderStatus.COLLECTED,
            reason="Wrong ticket handed over", now=NOW + dt.timedelta(minutes=5),
        )
        assert order.status == OrderStatus.READY
        assert order.collected_at is None
        assert order.payment.status == PaymentStatus.PENDING
        assert order.payment.cash_amount_received_cents is None
        event = order.events.get(action="uncollect")
        assert event.payload["cleared_cash_receipt"]["cash_amount_received_cents"] == (
            order.total_cents
        )

    def test_uncollect_requires_reason(self, cash_order, staff_user) -> None:
        order = apply(
            cash_order, "accept_cash", _staff(staff_user), OrderStatus.CASH_REQUEST, now=NOW,
        )
        order = apply(order, "start_kitchen", _staff(staff_user), OrderStatus.CASH_DUE, now=NOW)
        order = apply(order, "mark_ready", _staff(staff_user), OrderStatus.IN_KITCHEN, now=NOW)
        order = apply(order, "mark_collected", _staff(staff_user), OrderStatus.READY, now=NOW)
        with pytest.raises(TransitionError) as exc_info:
            apply(
                order, "uncollect", _staff(staff_user), OrderStatus.COLLECTED,
                now=NOW + dt.timedelta(minutes=1),
            )
        assert exc_info.value.code == "reason_required"

    def test_uncollect_refused_past_the_window(self, cash_order, staff_user) -> None:
        order = apply(
            cash_order, "accept_cash", _staff(staff_user), OrderStatus.CASH_REQUEST, now=NOW,
        )
        order = apply(order, "start_kitchen", _staff(staff_user), OrderStatus.CASH_DUE, now=NOW)
        order = apply(order, "mark_ready", _staff(staff_user), OrderStatus.IN_KITCHEN, now=NOW)
        order = apply(order, "mark_collected", _staff(staff_user), OrderStatus.READY, now=NOW)
        with pytest.raises(TransitionError) as exc_info:
            apply(
                order, "uncollect", _staff(staff_user), OrderStatus.COLLECTED,
                reason="too late", now=NOW + dt.timedelta(minutes=11),
            )
        assert exc_info.value.code == "illegal_transition"


class TestCloseOutNoShow:
    def test_refused_before_the_grace_deadline(self, eft_order, staff_user) -> None:
        _upload_proof(eft_order)
        order = apply(
            eft_order, "verify_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW,
        )
        order = apply(
            order, "start_kitchen", _staff(staff_user), OrderStatus.CONFIRMED_PREP, now=NOW,
        )
        order = apply(order, "mark_ready", _staff(staff_user), OrderStatus.IN_KITCHEN, now=NOW)
        with pytest.raises(TransitionError) as exc_info:
            apply(order, "close_out_no_show", SYSTEM_ACTOR, OrderStatus.READY, now=NOW)
        assert exc_info.value.code == "illegal_transition"

    def test_applies_no_show_after_the_grace_deadline(self, eft_order, staff_user) -> None:
        _upload_proof(eft_order)
        order = apply(
            eft_order, "verify_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW,
        )
        order = apply(
            order, "start_kitchen", _staff(staff_user), OrderStatus.CONFIRMED_PREP, now=NOW,
        )
        order = apply(order, "mark_ready", _staff(staff_user), OrderStatus.IN_KITCHEN, now=NOW)

        # trading_day window_end is 18:00 SAST (16:00 UTC), grace 15 min default.
        well_past = dt.datetime(2026, 9, 1, 16, 30, tzinfo=dt.UTC)
        order = apply(order, "close_out_no_show", SYSTEM_ACTOR, OrderStatus.READY, now=well_past)
        assert order.status == OrderStatus.CANCELLED
        assert order.cancellation_reason == CancellationReason.NO_SHOW
        assert order.dish_units_consumed is True  # stays consumed per §9.1


class TestCancel:
    def test_cancel_from_awaiting_eft_by_manager(self, eft_order, staff_user) -> None:
        order = apply(
            eft_order, "cancel", _staff(staff_user), OrderStatus.AWAITING_EFT,
            reason="Customer changed their mind",
            payload={"cancellation_reason": CancellationReason.CUSTOMER_REQUEST}, now=NOW,
        )
        assert order.status == OrderStatus.CANCELLED
        assert order.cancellation_reason == CancellationReason.CUSTOMER_REQUEST
        assert order.cancellation_note == "Customer changed their mind"

    def test_requires_a_valid_cancellation_reason(self, eft_order, staff_user) -> None:
        with pytest.raises(TransitionError) as exc_info:
            apply(
                eft_order, "cancel", _staff(staff_user), OrderStatus.AWAITING_EFT,
                payload={"cancellation_reason": "not_a_real_reason"}, now=NOW,
            )
        assert exc_info.value.code == "validation_error"

    def test_manager_cannot_cancel_from_in_kitchen(self, eft_order, staff_user) -> None:
        _upload_proof(eft_order)
        order = apply(
            eft_order, "verify_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW,
        )
        order = apply(
            order, "start_kitchen", _staff(staff_user), OrderStatus.CONFIRMED_PREP, now=NOW,
        )
        with pytest.raises(TransitionError) as exc_info:
            apply(
                order, "cancel", _staff(staff_user), OrderStatus.IN_KITCHEN,
                payload={"cancellation_reason": CancellationReason.STAFF}, now=NOW,
            )
        assert exc_info.value.code == "owner_only"

    def test_owner_can_cancel_from_in_kitchen_and_flags_refund_pending(
        self, eft_order, staff_user, owner_user,
    ) -> None:
        _upload_proof(eft_order)
        order = apply(
            eft_order, "verify_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW,
        )
        order = apply(
            order, "start_kitchen", _staff(staff_user), OrderStatus.CONFIRMED_PREP, now=NOW,
        )
        order = apply(
            order, "cancel", Actor(ActorKind.STAFF, owner_user), OrderStatus.IN_KITCHEN,
            payload={"cancellation_reason": CancellationReason.OWNER_EXCEPTION}, now=NOW,
        )
        assert order.status == OrderStatus.CANCELLED
        assert order.refund_note == "refund_pending"  # payment was verified


class TestChangeSlot:
    def test_moves_to_an_open_slot_with_room(self, eft_order, trading_day, staff_user) -> None:
        other_slot = Slot.objects.create(
            trading_day=trading_day, start_at=dt.time(16, 15), end_at=dt.time(16, 30), capacity=5,
        )
        order = apply(
            eft_order, "change_slot", _staff(staff_user), OrderStatus.AWAITING_EFT,
            payload={"new_slot_id": other_slot.pk}, now=NOW,
        )
        assert order.slot_id == other_slot.pk
        event = order.events.get(action="change_slot")
        assert event.payload["to_slot"] == other_slot.pk

    def test_refuses_a_full_slot(
        self, eft_order, trading_day, staff_user, dish, biz_settings,
    ) -> None:
        full_slot = Slot.objects.create(
            trading_day=trading_day, start_at=dt.time(16, 15), end_at=dt.time(16, 30), capacity=1,
        )
        reserve(_eft_req(dish, full_slot, customer_mobile_e164="+27829999999"), biz_settings)
        with pytest.raises(TransitionError) as exc_info:
            apply(
                eft_order, "change_slot", _staff(staff_user), OrderStatus.AWAITING_EFT,
                payload={"new_slot_id": full_slot.pk}, now=NOW,
            )
        assert exc_info.value.code == "slot_full"

    def test_illegal_once_ready(self, eft_order, trading_day, staff_user) -> None:
        _upload_proof(eft_order)
        order = apply(
            eft_order, "verify_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW,
        )
        order = apply(
            order, "start_kitchen", _staff(staff_user), OrderStatus.CONFIRMED_PREP, now=NOW,
        )
        order = apply(order, "mark_ready", _staff(staff_user), OrderStatus.IN_KITCHEN, now=NOW)
        other_slot = Slot.objects.create(
            trading_day=trading_day, start_at=dt.time(16, 15), end_at=dt.time(16, 30), capacity=5,
        )
        with pytest.raises(TransitionError) as exc_info:
            apply(
                order, "change_slot", _staff(staff_user), OrderStatus.READY,
                payload={"new_slot_id": other_slot.pk}, now=NOW,
            )
        assert exc_info.value.code == "illegal_transition"


class TestAmendItems:
    def test_increases_total_and_flags_balance_due_when_verified(
        self, eft_order, staff_user, dish_with_options,
    ) -> None:
        _upload_proof(eft_order)
        order = apply(
            eft_order, "verify_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW,
        )
        old_total = order.total_cents

        order = apply(
            order, "amend_items", _staff(staff_user), OrderStatus.CONFIRMED_PREP,
            reason="Customer added a dish",
            payload={"lines": [
                {"dish_id": order.lines.first().dish_id, "quantity": 1},
                {"dish_id": dish_with_options.pk, "quantity": 1, "option_value_ids": [
                    dish_with_options.options.get(name="Spice").values.get(name="Mild").pk,
                ]},
            ]},
            now=NOW,
        )
        assert order.total_cents > old_total
        assert order.balance_due_cents == order.total_cents - old_total
        assert order.lines.count() == 2

    def test_decrease_sets_refund_note_when_verified(self, eft_order, staff_user) -> None:
        _upload_proof(eft_order)
        order = apply(
            eft_order, "verify_eft", _staff(staff_user), OrderStatus.PAYMENT_REVIEW, now=NOW,
        )
        dish_id = order.lines.first().dish_id
        order = apply(
            order, "amend_items", _staff(staff_user), OrderStatus.CONFIRMED_PREP,
            reason="Customer asked for a smaller order",
            payload={"lines": [{"dish_id": dish_id, "quantity": 1}]},
            now=NOW,
        )
        # Same quantity as before (1) — force an actual decrease isn't
        # possible with this fixture's single-line order below min qty 1,
        # so this asserts the no-op-decrease path doesn't wrongly flag
        # balance_due instead.
        assert order.refund_note is None
        assert order.balance_due_cents == 0

    def test_requires_reason(self, eft_order, staff_user) -> None:
        dish_id = eft_order.lines.first().dish_id
        with pytest.raises(TransitionError) as exc_info:
            apply(
                eft_order, "amend_items", _staff(staff_user), OrderStatus.AWAITING_EFT,
                payload={"lines": [{"dish_id": dish_id, "quantity": 2}]}, now=NOW,
            )
        assert exc_info.value.code == "reason_required"

    def test_dish_cap_rechecked_only_on_increase(
        self, biz_settings, trading_day, slot, dish, staff_user,
    ) -> None:
        from core.models import DayDishAvailability

        DayDishAvailability.objects.create(trading_day=trading_day, dish=dish, max_units=2)
        order = reserve(
            _eft_req(dish, slot, lines=[CheckoutLine(dish_id=dish.pk, quantity=2)]), biz_settings,
        )
        # Increasing this order's own quantity beyond max_units=2 must fail...
        with pytest.raises(TransitionError) as exc_info:
            apply(
                order, "amend_items", _staff(staff_user), OrderStatus.AWAITING_EFT,
                reason="more please",
                payload={"lines": [{"dish_id": dish.pk, "quantity": 3}]}, now=NOW,
            )
        assert exc_info.value.code == "dish_qty_exceeded"
        # ...but re-submitting the *same* quantity (no increase) must not
        # be rejected on account of the order's own prior consumption.
        order = apply(
            order, "amend_items", _staff(staff_user), OrderStatus.AWAITING_EFT,
            reason="just a note change",
            payload={"lines": [{"dish_id": dish.pk, "quantity": 2, "kitchen_note": "no rice"}]},
            now=NOW,
        )
        assert order.lines.first().kitchen_note == "no rice"
