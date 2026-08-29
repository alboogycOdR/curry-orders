"""Integration tests for core/eft.py — the two §9.1 transitions milestone
4 needs (`proof_uploaded`, `expire_hold`). Orders are built through the
real `core.capacity.reserve()` transaction (not hand-inserted), so these
tests exercise the two modules together the same way the real checkout
flow does.
"""
from __future__ import annotations

import datetime as dt
import threading

import pytest

from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.eft import (
    EftError,
    check_proof_upload_throttle,
    expire_holds,
    record_proof_upload,
    record_proof_upload_attempt,
)
from core.models import ActorKind, OrderStatus, PaymentStatus

pytestmark = pytest.mark.django_db

NOW = dt.datetime(2026, 8, 31, 6, 0, tzinfo=dt.UTC)  # the day before trading_day's 2026-09-01


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


@pytest.fixture
def eft_order(biz_settings, trading_day, slot, dish):
    return reserve(_eft_req(dish, slot), biz_settings)


class TestProofUploadThrottle:
    def test_allows_up_to_the_limit(self) -> None:
        # `record_proof_upload_attempt`'s `occurred_at` is auto_now_add —
        # always the real wall clock, regardless of what `now` a caller
        # later passes to `check_proof_upload_throttle` — so the check
        # here has to use real "now" too (the default), not the fixed
        # fictional `NOW` other tests in this module use for `reserve()`.
        for _ in range(5):
            check_proof_upload_throttle("tok-a")
            record_proof_upload_attempt("tok-a")
        with pytest.raises(EftError) as exc_info:
            check_proof_upload_throttle("tok-a")
        assert exc_info.value.code == "throttled"
        assert exc_info.value.extra["retry_after_seconds"] == 3600

    def test_is_scoped_per_token(self) -> None:
        for _ in range(5):
            record_proof_upload_attempt("tok-b")
        # A different token has spent none of its own budget.
        check_proof_upload_throttle("tok-c", now=NOW)

    def test_old_attempts_fall_out_of_the_window(self) -> None:
        from core.models import ThrottleEvent

        for _ in range(5):
            record_proof_upload_attempt("tok-d")
        # `occurred_at` is auto_now_add (ignores any value passed to
        # .create()) — backdate via a queryset .update(), which bypasses
        # that, to simulate these attempts having happened over an hour
        # ago relative to `now=NOW`.
        ThrottleEvent.objects.filter(scope="proof_token", key="tok-d").update(
            occurred_at=NOW - dt.timedelta(hours=1, minutes=1)
        )
        check_proof_upload_throttle("tok-d", now=NOW)  # does not raise


class TestRecordProofUpload:
    def test_from_awaiting_eft_moves_to_payment_review(self, eft_order) -> None:
        media = record_proof_upload(
            eft_order,
            storage_key="proofs/test.jpg",
            mime_type="image/jpeg",
            byte_size=1234,
            sha256=b"\x00" * 32,
            now=NOW,
        )
        eft_order.refresh_from_db()
        assert eft_order.status == OrderStatus.PAYMENT_REVIEW
        assert eft_order.payment.status == PaymentStatus.UNDER_REVIEW
        assert eft_order.payment.current_proof_media_id == media.pk
        assert eft_order.payment.proof_uploaded_at == NOW

    def test_writes_an_audit_event(self, eft_order) -> None:
        record_proof_upload(
            eft_order, storage_key="proofs/test.jpg", mime_type="image/jpeg",
            byte_size=1234, sha256=b"\x00" * 32, now=NOW,
        )
        event = eft_order.events.get(action="proof_uploaded")
        assert event.from_status == OrderStatus.AWAITING_EFT
        assert event.to_status == OrderStatus.PAYMENT_REVIEW
        assert event.actor_kind == ActorKind.CUSTOMER
        assert event.payload["mime_type"] == "image/jpeg"

    def test_a_second_upload_from_payment_review_stays_legal(self, eft_order) -> None:
        # §9.1: proof_uploaded is legal from *both* awaiting_eft and
        # payment_review (a re-upload after a first attempt), always
        # landing on payment_review.
        record_proof_upload(
            eft_order, storage_key="proofs/first.jpg", mime_type="image/jpeg",
            byte_size=100, sha256=b"\x01" * 32, now=NOW,
        )
        eft_order.refresh_from_db()
        media2 = record_proof_upload(
            eft_order, storage_key="proofs/second.jpg", mime_type="image/png",
            byte_size=200, sha256=b"\x02" * 32, now=NOW,
        )
        eft_order.refresh_from_db()
        assert eft_order.status == OrderStatus.PAYMENT_REVIEW
        assert eft_order.payment.current_proof_media_id == media2.pk

    def test_illegal_from_a_terminal_status(self, eft_order) -> None:
        eft_order.status = OrderStatus.COLLECTED
        eft_order.save(update_fields=["status"])
        with pytest.raises(EftError) as exc_info:
            record_proof_upload(
                eft_order, storage_key="proofs/x.jpg", mime_type="image/jpeg",
                byte_size=1, sha256=b"\x00" * 32, now=NOW,
            )
        assert exc_info.value.code == "illegal_transition"


class TestExpireHolds:
    def test_expires_a_lapsed_awaiting_eft_hold(self, eft_order) -> None:
        eft_order.hold_expires_at = NOW - dt.timedelta(minutes=1)
        eft_order.save(update_fields=["hold_expires_at"])

        count = expire_holds(now=NOW)

        eft_order.refresh_from_db()
        assert count == 1
        assert eft_order.status == OrderStatus.PAYMENT_EXPIRED
        assert eft_order.payment.status == PaymentStatus.EXPIRED
        event = eft_order.events.get(action="expire_hold")
        assert event.actor_kind == ActorKind.SYSTEM
        assert event.from_status == OrderStatus.AWAITING_EFT
        assert event.to_status == OrderStatus.PAYMENT_EXPIRED

    def test_does_not_touch_a_hold_that_has_not_lapsed_yet(self, eft_order) -> None:
        # eft_order's hold_expires_at is NOW + eft_hold_minutes from reserve().
        count = expire_holds(now=NOW)
        eft_order.refresh_from_db()
        assert count == 0
        assert eft_order.status == OrderStatus.AWAITING_EFT

    def test_never_touches_payment_review(self, eft_order) -> None:
        # Edge case 6 (§20.4): proof uploaded right before the hold would
        # have lapsed — expire_holds must leave it alone entirely.
        record_proof_upload(
            eft_order, storage_key="proofs/x.jpg", mime_type="image/jpeg",
            byte_size=1, sha256=b"\x00" * 32, now=NOW,
        )
        eft_order.refresh_from_db()
        # hold_expires_at is untouched by proof_uploaded and still in the
        # past relative to a far-future "now".
        far_future = NOW + dt.timedelta(days=1)
        count = expire_holds(now=far_future)
        eft_order.refresh_from_db()
        assert count == 0
        assert eft_order.status == OrderStatus.PAYMENT_REVIEW

    def test_batch_size_caps_one_run(self, biz_settings, trading_day, dish) -> None:
        from core.models import Order, Slot

        base = dt.datetime.combine(dt.date(2026, 1, 1), dt.time(16, 0))
        orders = []
        for i in range(3):
            start = (base + dt.timedelta(minutes=15 * i)).time()
            end = (base + dt.timedelta(minutes=15 * (i + 1))).time()
            s = Slot.objects.create(
                trading_day=trading_day, start_at=start, end_at=end, capacity=5,
            )
            order = reserve(_eft_req(dish, s, customer_mobile_e164=f"+2782123456{i}"), biz_settings)
            order.hold_expires_at = NOW - dt.timedelta(minutes=1)
            order.save(update_fields=["hold_expires_at"])
            orders.append(order)

        count = expire_holds(now=NOW, batch_size=2)
        assert count == 2
        expired = Order.objects.filter(
            pk__in=[o.pk for o in orders], status=OrderStatus.PAYMENT_EXPIRED,
        ).count()
        assert expired == 2


@pytest.mark.django_db(transaction=True)
class TestExpireHoldsConcurrency:
    def test_two_concurrent_runs_each_expire_a_lapsed_hold_exactly_once(
        self, biz_settings, trading_day, slot, dish,
    ) -> None:
        # Real separate transactions per thread (django_db(transaction=True),
        # same reasoning as test_capacity.py's own concurrency tests) — a
        # naive "select then update" expire_holds could double-fire on the
        # same order if two scheduler ticks ever overlapped; select_for_update
        # inside _expire_one_hold is what this test is actually proving.
        order = reserve(_eft_req(dish, slot), biz_settings)
        order.hold_expires_at = NOW - dt.timedelta(minutes=1)
        order.save(update_fields=["hold_expires_at"])

        results = []

        def run() -> None:
            import django

            django.db.close_old_connections()
            results.append(expire_holds(now=NOW))

        threads = [threading.Thread(target=run) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results) == 1  # exactly one run actually expired it
        order.refresh_from_db()
        assert order.status == OrderStatus.PAYMENT_EXPIRED
        assert order.events.filter(action="expire_hold").count() == 1
