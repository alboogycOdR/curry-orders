"""Integration tests for core/capacity.py (spec §8) — not wired to any
view yet (see that module's own docstring); tested directly since it's
the highest-stakes code in the project ("This is the critical backend").

The concurrency test uses `django_db(transaction=True)` (real, separate
transactions per thread — the default `db` fixture's single wrapping
transaction would hide row-lock contention) to actually race two
`reserve()` calls against the same slot, per spec §20.5's own test-plan
line: "integration/ # capacity transactions under concurrency".
"""
from __future__ import annotations

import datetime as dt
import threading

import pytest

from core.capacity import (
    CapacityError,
    CheckoutLine,
    ReservationRequest,
    check_cash,
    check_cutoff,
    check_day_cap,
    check_day_open,
    check_horizon,
    check_slot_cap,
    check_slot_open,
    dish_units_used,
    reserve,
)
from core.models import (
    DayDishAvailability,
    Order,
    OrderLine,
    Payment,
    Slot,
    TradingDay,
)

pytestmark = pytest.mark.django_db

NOW = dt.datetime(2026, 8, 31, 6, 0, tzinfo=dt.UTC)  # the day *before* trading_day's 2026-09-01 —
# ordering ahead, not same-day, so check_cutoff's "today" branch never applies here regardless of
# what SAST time this maps to; tests that specifically exercise cutoff pass their own `now`.


def _req(dish, slot, **overrides) -> ReservationRequest:
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


class TestSimpleCeilingChecks:
    def test_day_closed(self) -> None:
        td = TradingDay(is_open=False)
        with pytest.raises(CapacityError) as exc:
            check_day_open(td)
        assert exc.value.code == "day_closed"

    def test_horizon_before_today(self) -> None:
        with pytest.raises(CapacityError) as exc:
            check_horizon(dt.date(2026, 8, 31), dt.date(2026, 9, 1), 7)
        assert exc.value.code == "outside_horizon"

    def test_horizon_beyond_preorder_days(self) -> None:
        with pytest.raises(CapacityError) as exc:
            check_horizon(dt.date(2026, 9, 9), dt.date(2026, 9, 1), 7)
        assert exc.value.code == "outside_horizon"

    def test_horizon_today_and_last_day_are_both_fine(self) -> None:
        check_horizon(dt.date(2026, 9, 1), dt.date(2026, 9, 1), 7)
        check_horizon(dt.date(2026, 9, 8), dt.date(2026, 9, 1), 7)

    def test_cutoff_passed_at_exactly_cutoff_time(self) -> None:
        # D-05: "at exactly 10:00:00 today is closed" — strict >=.
        with pytest.raises(CapacityError) as exc:
            check_cutoff(
                dt.date(2026, 9, 1), dt.date(2026, 9, 1), dt.time(10, 0, 0), dt.time(10, 0)
            )
        assert exc.value.code == "cutoff_passed"

    def test_cutoff_fine_one_second_before(self) -> None:
        check_cutoff(dt.date(2026, 9, 1), dt.date(2026, 9, 1), dt.time(9, 59, 59), dt.time(10, 0))

    def test_cutoff_irrelevant_for_a_future_date(self) -> None:
        check_cutoff(dt.date(2026, 9, 5), dt.date(2026, 9, 1), dt.time(23, 0), dt.time(10, 0))

    def test_slot_closed(self) -> None:
        with pytest.raises(CapacityError) as exc:
            check_slot_open(Slot(is_closed=True))
        assert exc.value.code == "slot_closed"


class TestDayAndSlotCaps:
    def test_day_cap_ok_when_under(self, trading_day) -> None:
        check_day_cap(trading_day)  # 0 occupying < 100 default cap

    def test_day_cap_full(self, trading_day, slot, dish) -> None:
        trading_day.daily_order_cap = 0
        trading_day.save(update_fields=["daily_order_cap"])
        with pytest.raises(CapacityError) as exc:
            check_day_cap(trading_day)
        assert exc.value.code == "day_full"

    def test_slot_cap_full(self, slot) -> None:
        slot.capacity = 0
        slot.save(update_fields=["capacity"])
        with pytest.raises(CapacityError) as exc:
            check_slot_cap(slot)
        assert exc.value.code == "slot_full"


class TestCashCeiling:
    def test_non_cash_is_a_no_op(self, trading_day, biz_settings) -> None:
        check_cash(trading_day, biz_settings, dt.date(2026, 9, 1), "eft")

    def test_cash_disabled(self, trading_day, biz_settings) -> None:
        biz_settings.cash_enabled = False
        with pytest.raises(CapacityError) as exc:
            check_cash(trading_day, biz_settings, dt.date(2026, 9, 1), "cash")
        assert exc.value.code == "cash_not_allowed"

    def test_cash_same_day_only_blocks_future_date(self, trading_day, biz_settings) -> None:
        biz_settings.cash_same_day_only = True
        with pytest.raises(CapacityError) as exc:
            # today (2026-08-30) != trading_day.date (2026-09-01)
            check_cash(trading_day, biz_settings, dt.date(2026, 8, 30), "cash")
        assert exc.value.code == "cash_not_allowed"

    def test_cash_cap_reached(self, trading_day, biz_settings) -> None:
        biz_settings.cash_daily_cap = 0
        with pytest.raises(CapacityError) as exc:
            check_cash(trading_day, biz_settings, trading_day.date, "cash")
        assert exc.value.code == "cash_cap"


class TestDishUnitsUsed:
    def test_zero_when_nothing_ordered(self, trading_day, dish) -> None:
        assert dish_units_used(trading_day, [dish.pk]) == {}


class TestReserveHappyPath:
    def test_creates_order_lines_payment_and_event(
        self, trading_day, slot, dish, biz_settings
    ) -> None:
        order = reserve(_req(dish, slot), biz_settings)

        assert order.order_number == "CT-260901-0001"
        assert order.status == "awaiting_eft"
        assert order.payment_method == "eft"
        assert order.hold_expires_at == NOW + dt.timedelta(minutes=biz_settings.eft_hold_minutes)
        assert order.subtotal_cents == dish.price_cents
        assert order.total_cents == dish.price_cents

        assert OrderLine.objects.filter(order=order).count() == 1
        line = OrderLine.objects.get(order=order)
        assert line.dish_name_snapshot == dish.name
        assert line.unit_price_cents_snapshot == dish.price_cents

        payment = Payment.objects.get(order=order)
        assert payment.status == "pending"
        assert payment.amount_cents == order.total_cents

        assert order.events.count() == 1
        assert order.events.first().action == "checkout"

    def test_cash_checkout_has_no_hold(self, trading_day, slot, dish, biz_settings) -> None:
        # Cash is same-day-only by default (D-06) — unlike the other
        # happy-path tests, this one needs `now` to land *on*
        # trading_day's date, before its 10:00 cut-off (07:00 SAST here).
        same_day_before_cutoff = dt.datetime(2026, 9, 1, 5, 0, tzinfo=dt.UTC)
        req = _req(dish, slot, payment_method="cash", now=same_day_before_cutoff)
        order = reserve(req, biz_settings)
        assert order.status == "cash_request"
        assert order.hold_expires_at is None

    def test_second_order_same_day_gets_next_sequence(
        self, trading_day, slot, dish, biz_settings
    ) -> None:
        reserve(_req(dish, slot), biz_settings)
        second_slot = Slot.objects.create(
            trading_day=trading_day, start_at=dt.time(16, 15), end_at=dt.time(16, 30), capacity=13
        )
        order2 = reserve(_req(dish, second_slot), biz_settings)
        assert order2.order_number == "CT-260901-0002"

    def test_customer_upserted_by_mobile(self, trading_day, slot, dish, biz_settings) -> None:
        from core.models import Customer

        reserve(_req(dish, slot), biz_settings)
        assert Customer.objects.filter(mobile_e164="+27821234567").count() == 1
        customer = Customer.objects.get(mobile_e164="+27821234567")
        assert customer.order_count == 1

        second_slot = Slot.objects.create(
            trading_day=trading_day, start_at=dt.time(16, 15), end_at=dt.time(16, 30), capacity=13
        )
        reserve(_req(dish, second_slot, customer_name="Jane Newname"), biz_settings)
        customer.refresh_from_db()
        assert customer.order_count == 2
        assert customer.full_name == "Jane Newname"

    def test_priced_from_current_dish_price_not_a_cached_one(
        self, trading_day, slot, dish, biz_settings
    ) -> None:
        dish.price_cents = 9999
        dish.save(update_fields=["price_cents"])
        order = reserve(_req(dish, slot), biz_settings)
        assert order.total_cents == 9999

    def test_option_pricing_and_option_key(
        self, trading_day, slot, dish_with_options, biz_settings
    ) -> None:
        hot = dish_with_options.options.get(name="Spice").values.get(name="Hot")
        cheese = dish_with_options.options.get(name="Extra cheese").values.get(name="Yes")
        req = _req(
            dish_with_options, slot,
            lines=[CheckoutLine(dish_id=dish_with_options.pk, quantity=1,
                                 option_value_ids=[hot.pk, cheese.pk])],
        )
        order = reserve(req, biz_settings)
        line = OrderLine.objects.get(order=order)
        assert line.option_key == "Extra cheese=Yes|Spice=Hot"
        assert line.unit_price_cents_snapshot == dish_with_options.price_cents + 1500


class TestReserveCeilingFailures:
    def test_unknown_day_raises_day_closed(self, dish, biz_settings) -> None:
        req = _req(dish, type("S", (), {"pk": 1})())
        req.trading_day_date = dt.date(2099, 1, 1)
        with pytest.raises(CapacityError) as exc:
            reserve(req, biz_settings)
        assert exc.value.code == "day_closed"

    def test_closed_day(self, trading_day, slot, dish, biz_settings) -> None:
        trading_day.is_open = False
        trading_day.save(update_fields=["is_open"])
        with pytest.raises(CapacityError) as exc:
            reserve(_req(dish, slot), biz_settings)
        assert exc.value.code == "day_closed"

    def test_dish_unavailable_for_the_day(self, trading_day, slot, dish, biz_settings) -> None:
        DayDishAvailability.objects.create(trading_day=trading_day, dish=dish, is_available=False)
        with pytest.raises(CapacityError) as exc:
            reserve(_req(dish, slot), biz_settings)
        assert exc.value.code == "dish_unavailable"
        assert exc.value.line_index == 0

    def test_dish_qty_exceeded(self, trading_day, slot, dish, biz_settings) -> None:
        DayDishAvailability.objects.create(trading_day=trading_day, dish=dish, max_units=1)
        req = _req(dish, slot, lines=[CheckoutLine(dish_id=dish.pk, quantity=2)])
        with pytest.raises(CapacityError) as exc:
            reserve(req, biz_settings)
        assert exc.value.code == "dish_qty_exceeded"

    def test_slot_full(self, trading_day, slot, dish, biz_settings) -> None:
        slot.capacity = 1
        slot.save(update_fields=["capacity"])
        reserve(_req(dish, slot), biz_settings)  # fills the one spot
        # a second, still-open slot so the second reserve() doesn't also collide on the dish cap
        Slot.objects.create(
            trading_day=trading_day, start_at=dt.time(17, 0), end_at=dt.time(17, 15), capacity=13
        )
        with pytest.raises(CapacityError) as exc:
            reserve(_req(dish, slot), biz_settings)
        assert exc.value.code == "slot_full"
        assert "slots" in exc.value.alternatives  # the second, still-open slot is offered

    def test_day_full(self, trading_day, slot, dish, biz_settings) -> None:
        trading_day.daily_order_cap = 1
        trading_day.save(update_fields=["daily_order_cap"])
        second_slot = Slot.objects.create(
            trading_day=trading_day, start_at=dt.time(16, 15), end_at=dt.time(16, 30), capacity=13
        )
        reserve(_req(dish, slot), biz_settings)
        with pytest.raises(CapacityError) as exc:
            reserve(_req(dish, second_slot), biz_settings)
        assert exc.value.code == "day_full"

    def test_no_lines_is_a_validation_error(self, trading_day, slot, dish, biz_settings) -> None:
        req = _req(dish, slot, lines=[])
        with pytest.raises(CapacityError) as exc:
            reserve(req, biz_settings)
        assert exc.value.code == "validation_error"

    def test_cash_same_day_only_blocks_a_future_date(self, biz_settings) -> None:
        future = dt.date(2026, 9, 5)
        td = TradingDay.objects.create(
            date=future, is_open=True, window_start=dt.time(16, 0), window_end=dt.time(18, 0),
            cutoff_time=dt.time(10, 0), daily_order_cap=100,
        )
        slot = Slot.objects.create(
            trading_day=td, start_at=dt.time(16, 0), end_at=dt.time(16, 15), capacity=13
        )
        dish = __import__("core.models", fromlist=["Dish"]).Dish.objects.create(
            slug="x", name="X", category="C", price_cents=100, is_active_on_menu=True
        )
        req = _req(dish, slot, trading_day_date=future, payment_method="cash",
                    now=dt.datetime(2026, 9, 1, 12, 0, tzinfo=dt.UTC))
        with pytest.raises(CapacityError) as exc:
            reserve(req, biz_settings)
        assert exc.value.code == "cash_not_allowed"


class TestAssistedAfterCutoff:
    # `check_after_cutoff_permission` only has anything to say when the
    # order targets *today* (trading_day.date) — same-day, after the
    # default 10:00 SAST cut-off (noon SAST = 10:00 UTC), unlike `NOW`
    # (the day before, for every other test in this file).
    SAME_DAY_AFTER_CUTOFF = dt.datetime(2026, 9, 1, 10, 0, tzinfo=dt.UTC)

    def test_disabled_by_default(self, trading_day, slot, dish, biz_settings, staff_user) -> None:
        req = _req(
            dish, slot, is_staff_assisted=True, after_cutoff_reason="phoned in",
            created_by_user=staff_user, now=self.SAME_DAY_AFTER_CUTOFF,
        )
        # assisted_after_cutoff_enabled is False by default (D-11) — a
        # different code than a customer checkout would get for the same
        # timing (cutoff_passed), since staff go through this permission
        # check instead of check_cutoff.
        with pytest.raises(CapacityError) as exc:
            reserve(req, biz_settings)
        assert exc.value.code == "after_cutoff_disabled"

    def test_reason_required_when_enabled(
        self, trading_day, slot, dish, biz_settings, staff_user
    ) -> None:
        biz_settings.assisted_after_cutoff_enabled = True
        biz_settings.save(update_fields=["assisted_after_cutoff_enabled"])
        req = _req(
            dish, slot, is_staff_assisted=True, after_cutoff_reason=None,
            created_by_user=staff_user, now=self.SAME_DAY_AFTER_CUTOFF,
        )
        with pytest.raises(CapacityError) as exc:
            reserve(req, biz_settings)
        assert exc.value.code == "reason_required"

    def test_succeeds_when_enabled_with_reason(
        self, trading_day, slot, dish, biz_settings, staff_user
    ) -> None:
        biz_settings.assisted_after_cutoff_enabled = True
        biz_settings.save(update_fields=["assisted_after_cutoff_enabled"])
        req = _req(
            dish, slot, is_staff_assisted=True, after_cutoff_reason="phoned in",
            created_by_user=staff_user, now=self.SAME_DAY_AFTER_CUTOFF,
        )
        order = reserve(req, biz_settings)
        assert order.after_cutoff_reason == "phoned in"
        assert order.created_by_user_id == staff_user.pk


@pytest.mark.django_db(transaction=True)
class TestConcurrency:
    """Real, separate transactions per thread (not the default `db`
    fixture's single wrapping transaction) so `SELECT ... FOR UPDATE`
    contention is actually exercised — spec §20.5's own line:
    "integration/ # capacity transactions under concurrency".
    """

    def test_two_concurrent_checkouts_for_the_last_slot_spot_only_one_wins(self) -> None:
        from django.db import connections

        from core.materialise import materialise_day
        from core.models import Dish, Settings

        settings = Settings.objects.create(id=1, public_site_name="Test")
        trading_day = materialise_day(dt.date(2026, 9, 1), settings)
        slot = trading_day.slots.order_by("start_at").first()
        slot.capacity = 1
        slot.save(update_fields=["capacity"])
        dish = Dish.objects.create(
            slug="race-dish", name="Race Dish", category="C", price_cents=1000,
            is_active_on_menu=True,
        )

        results: list[object] = [None, None]

        def attempt(i: int) -> None:
            try:
                req = _req(dish, slot, customer_mobile_e164=f"+2782000000{i}")
                reserve(req, settings)
                results[i] = "ok"
            except CapacityError as e:
                results[i] = e.code
            finally:
                connections.close_all()  # each thread gets its own connection; don't leak it

        t1 = threading.Thread(target=attempt, args=(0,))
        t2 = threading.Thread(target=attempt, args=(1,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert sorted(results) == ["ok", "slot_full"]
        assert Order.objects.filter(status="awaiting_eft").count() == 1

    def test_dish_unit_cap_race(self) -> None:
        from django.db import connections

        from core.materialise import materialise_day
        from core.models import Dish, Settings

        settings = Settings.objects.create(id=1, public_site_name="Test")
        trading_day = materialise_day(dt.date(2026, 9, 1), settings)
        slots = list(trading_day.slots.order_by("start_at")[:2])
        dish = Dish.objects.create(
            slug="capped-dish", name="Capped Dish", category="C", price_cents=1000,
            is_active_on_menu=True,
        )
        DayDishAvailability.objects.create(trading_day=trading_day, dish=dish, max_units=1)

        results: list[object] = [None, None]

        def attempt(i: int) -> None:
            try:
                req = _req(dish, slots[i], customer_mobile_e164=f"+2782000001{i}")
                reserve(req, settings)
                results[i] = "ok"
            except CapacityError as e:
                results[i] = e.code
            finally:
                connections.close_all()

        t1 = threading.Thread(target=attempt, args=(0,))
        t2 = threading.Thread(target=attempt, args=(1,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert sorted(results) == ["dish_qty_exceeded", "ok"]
