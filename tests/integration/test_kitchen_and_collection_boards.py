"""Integration tests for the kitchen desk and collection board
(spec §12.4/§12.5, milestone 6) — `staff/views.py`'s `kitchen`/
`collection_board`, and `staff/api.py`'s `lock_prep_list`/`close_out_day`.
Board membership (§9.3), the summary aggregate, the exceptions band, and
"Close out day" are all real `core.Order` queries now, not sample data.
"""
from __future__ import annotations

import datetime as dt

import pytest
from django.urls import reverse

from core.auth import hash_password
from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.eft import record_proof_upload
from core.models import ActorKind, OrderStatus, TradingDay, User, UserRole
from core.transitions import Actor, apply
from core.tz import now_sast

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple"
NOW = dt.datetime(2026, 8, 31, 6, 0, tzinfo=dt.UTC)  # day before trading_day's 2026-09-01


def _make_staff(**overrides) -> User:
    defaults = dict(
        email="manager@example.test", name="Manager", role=UserRole.MANAGER,
        password_hash=hash_password(PASSWORD), must_change_password=False,
    )
    defaults.update(overrides)
    return User.objects.create(**defaults)


def _staff_actor() -> Actor:
    staff = User.objects.filter(role=UserRole.MANAGER).first() or _make_staff()
    return Actor(ActorKind.STAFF, staff)


def _login(client, email: str = "manager@example.test") -> None:
    resp = client.post(reverse("manage:login"), {"email": email, "password": PASSWORD})
    assert resp.status_code == 302


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


def _confirmed_order(dish, slot, biz_settings, **overrides):
    """An order verified onto the kitchen board (`confirmed_prep`)."""
    order = reserve(_eft_req(dish, slot, **overrides), biz_settings)
    record_proof_upload(
        order, storage_key=f"p-{order.pk}.jpg", mime_type="image/jpeg", byte_size=1,
        sha256=f"order-{order.pk}".encode().ljust(32, b"\x00"), now=NOW,
    )
    order.refresh_from_db()
    return apply(order, "verify_eft", _staff_actor(), OrderStatus.PAYMENT_REVIEW, now=NOW)


def _past_deadline_trading_day(biz_settings, dish, *, payment_method: str = "eft"):
    """A trading day whose window_end + grace has already passed
    relative to the *real* wall clock (`now_sast()`, not a frozen
    value — this project has no freezegun dependency), with one order
    walked all the way to `ready`. Used by the collection-board/close-out
    tests, which all need this same "it's now past the deadline" setup.
    """
    now = now_sast()
    # `placed` is the moment the order goes in; every time-of-day below is
    # derived from it so the whole window sits inside ONE calendar day.
    # Shortly after midnight "now - 2h" is yesterday, and stamping its
    # .time() onto today's date would put the window in the FUTURE (and,
    # for cash, make the order's date mismatch the trading day — tripping
    # the same-day-only rule). Anchor on yesterday evening instead: still
    # entirely in the past relative to the real wall clock, which is all
    # these tests need.
    if now.hour < 3:
        placed = (now - dt.timedelta(days=1)).replace(
            hour=20, minute=0, second=0, microsecond=0
        )
    else:
        placed = now - dt.timedelta(hours=2)
    trading_day = TradingDay.objects.create(
        date=placed.date(), is_open=True,
        window_start=placed.time(),
        window_end=(placed + dt.timedelta(hours=1)).time(),
        # 23:59, not 00:00 — the order below is placed at `placed`, same
        # calendar day; check_cutoff needs that time-of-day to still be
        # before cutoff, or reserve() itself would refuse it.
        cutoff_time=dt.time(23, 59), daily_order_cap=50,
    )
    slot = trading_day.slots.create(
        start_at=(placed + dt.timedelta(minutes=90)).time(),
        end_at=(placed + dt.timedelta(minutes=105)).time(),
        capacity=5,
    )
    order = reserve(
        ReservationRequest(
            trading_day_date=trading_day.date, slot_id=slot.pk, payment_method=payment_method,
            customer_name="Jane Customer", customer_mobile_e164="+27821234567",
            lines=[CheckoutLine(dish_id=dish.pk, quantity=1)], now=placed,
        ),
        biz_settings,
    )
    actor = _staff_actor()
    if payment_method == "eft":
        record_proof_upload(
            order, storage_key="p.jpg", mime_type="image/jpeg", byte_size=1,
            sha256=b"\x00" * 32, now=now,
        )
        order.refresh_from_db()
        order = apply(order, "verify_eft", actor, OrderStatus.PAYMENT_REVIEW, now=now)
    else:
        order = apply(order, "accept_cash", actor, OrderStatus.CASH_REQUEST, now=now)
    order = apply(order, "start_kitchen", actor, order.status, now=now)
    order = apply(order, "mark_ready", actor, OrderStatus.IN_KITCHEN, now=now)
    return trading_day, order


class TestKitchenBoard:
    def test_anonymous_redirected_to_login(self, client) -> None:
        resp = client.get(reverse("manage:kitchen"))
        assert resp.status_code == 302

    def test_no_trading_day_shows_the_empty_state(self, client) -> None:
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:kitchen"), {"date": "2099-01-01"})
        assert resp.status_code == 200
        assert b"No trading day exists" in resp.content

    def test_summary_groups_and_sums_by_dish_and_option(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        order_a = _confirmed_order(dish, slot, biz_settings, customer_mobile_e164="+27821111111")
        order_b = _confirmed_order(dish, slot, biz_settings, customer_mobile_e164="+27822222222")

        _login(client)
        resp = client.get(reverse("manage:kitchen"), {"date": trading_day.date.isoformat()})
        content = resp.content.decode()
        assert "&times;2" in content  # 1 + 1 units of the same dish, no options
        assert order_a.order_number in content
        assert order_b.order_number in content

    def test_never_shows_non_board_statuses(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        awaiting = reserve(_eft_req(dish, slot), biz_settings)  # still awaiting_eft
        resp = client.get(reverse("manage:kitchen"), {"date": trading_day.date.isoformat()})
        assert awaiting.order_number.encode() not in resp.content

    def test_exceptions_band_flags_note_kitchen_note_and_allergen(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        dish.allergen_text = "Contains peanuts"
        dish.save(update_fields=["allergen_text"])
        order = _confirmed_order(dish, slot, biz_settings, note="Ring the bell")
        _login(client)
        resp = client.get(reverse("manage:kitchen"), {"date": trading_day.date.isoformat()})
        content = resp.content.decode()
        assert "Ring the bell" in content
        assert "Contains peanuts" in content
        assert order.order_number in content

    def test_added_after_lock_band(self, client, biz_settings, trading_day, slot, dish) -> None:
        _make_staff()
        trading_day.kitchen_locked_at = NOW - dt.timedelta(minutes=5)
        trading_day.save(update_fields=["kitchen_locked_at"])
        order = _confirmed_order(dish, slot, biz_settings)  # confirmed_at == NOW, after the lock
        _login(client)
        resp = client.get(reverse("manage:kitchen"), {"date": trading_day.date.isoformat()})
        content = resp.content.decode()
        assert "Added after lock" in content
        assert order.order_number in content


class TestLockPrepList:
    def _url(self, date: dt.date) -> str:
        return reverse("manage:api_lock_prep_list", args=[date.isoformat()])

    def test_locks_and_is_idempotent(self, client, trading_day) -> None:
        _make_staff()
        _login(client)
        assert trading_day.kitchen_locked_at is None

        resp = client.post(self._url(trading_day.date))
        assert resp.status_code == 200
        trading_day.refresh_from_db()
        first_lock = trading_day.kitchen_locked_at
        assert first_lock is not None
        assert trading_day.kitchen_locked_by_id is not None

        resp2 = client.post(self._url(trading_day.date))
        assert resp2.status_code == 200
        trading_day.refresh_from_db()
        assert trading_day.kitchen_locked_at == first_lock  # unchanged, not re-locked

    def test_unknown_date_is_404(self, client) -> None:
        _make_staff()
        _login(client)
        resp = client.post(reverse("manage:api_lock_prep_list", args=["2099-01-01"]))
        assert resp.status_code == 404


class TestCollectionBoard:
    def test_anonymous_redirected_to_login(self, client) -> None:
        resp = client.get(reverse("manage:collection"))
        assert resp.status_code == 302

    def test_groups_ready_orders_by_slot(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        order = _confirmed_order(dish, slot, biz_settings)
        actor = _staff_actor()
        order = apply(order, "start_kitchen", actor, OrderStatus.CONFIRMED_PREP, now=NOW)
        order = apply(order, "mark_ready", actor, OrderStatus.IN_KITCHEN, now=NOW)

        _login(client)
        resp = client.get(reverse("manage:collection"), {"date": trading_day.date.isoformat()})
        content = resp.content.decode()
        assert order.order_number in content
        assert "16:00" in content  # slot.start_at

    def test_uncollected_bucket_past_the_grace_deadline(self, client, biz_settings, dish) -> None:
        _make_staff()
        trading_day, order = _past_deadline_trading_day(biz_settings, dish)

        _login(client)
        resp = client.get(reverse("manage:collection"), {"date": trading_day.date.isoformat()})
        content = resp.content.decode()
        assert "Uncollected" in content
        assert "Close out day" in content
        assert order.order_number in content


class TestCloseOutDayApi:
    def _url(self, date: dt.date) -> str:
        return reverse("manage:api_close_out_day", args=[date.isoformat()])

    def test_noop_before_the_grace_deadline(self, client, trading_day) -> None:
        _make_staff()
        _login(client)
        resp = client.post(self._url(trading_day.date))
        assert resp.status_code == 200
        assert resp.json()["closed"] == 0

    def test_unknown_date_is_404(self, client) -> None:
        _make_staff()
        _login(client)
        resp = client.post(reverse("manage:api_close_out_day", args=["2099-01-01"]))
        assert resp.status_code == 404

    def test_closes_out_ready_orders_and_sets_closed_out_at(
        self, client, biz_settings, dish,
    ) -> None:
        _make_staff()
        trading_day, order = _past_deadline_trading_day(biz_settings, dish)

        _login(client)
        resp = client.post(self._url(trading_day.date))
        assert resp.status_code == 200
        assert resp.json()["closed"] == 1
        order.refresh_from_db()
        trading_day.refresh_from_db()
        assert order.status == OrderStatus.CANCELLED
        assert trading_day.closed_out_at is not None


class TestCloseOutDaysJob:
    def test_run_close_out_days_task(self, biz_settings, dish, monkeypatch) -> None:
        from core.models import JobHeartbeat

        import jobs.tasks as jobs_tasks

        trading_day, order = _past_deadline_trading_day(biz_settings, dish, payment_method="cash")

        # The job scopes itself to "today's" trading day (it fires 23:30
        # SAST on the day that's ending). The helper anchors on yesterday
        # when the real clock is just past midnight, so pin the job's
        # clock to 23:30 on the trading day itself — the moment the
        # scheduler actually runs it. `close_out_day`'s own grace-deadline
        # check still uses the real wall clock, which is already past.
        from core.tz import SAST

        monkeypatch.setattr(
            jobs_tasks, "now_sast",
            lambda: dt.datetime.combine(trading_day.date, dt.time(23, 30), tzinfo=SAST),
        )

        jobs_tasks.run_close_out_days()

        order.refresh_from_db()
        assert order.status == OrderStatus.CANCELLED
        heartbeat = JobHeartbeat.objects.get(job_name="close_out_days")
        assert heartbeat.last_ok is True
        assert "1 order(s) closed out" in heartbeat.detail

    def test_a_quiet_run_still_records_ok(self) -> None:
        from core.models import JobHeartbeat
        from jobs.tasks import run_close_out_days

        run_close_out_days()  # no trading day exists for "today" at all
        heartbeat = JobHeartbeat.objects.get(job_name="close_out_days")
        assert heartbeat.last_ok is True
