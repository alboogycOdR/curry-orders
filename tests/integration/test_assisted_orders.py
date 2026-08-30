"""Integration tests for §12.9's assisted order entry
(`staff/views.py::assisted_order_new`, `/manage/orders/new/`) — capacity
parity with web checkout, after-cut-off gating + mandatory reason
(D-11), the EFT escalation branches (`payment_review`/`confirmed_prep`,
D-18), and cash following M7's own rules.
"""
from __future__ import annotations

import datetime as dt

import pytest
from django.urls import reverse

from core.auth import hash_password
from core.models import ActorKind, Order, OrderSource, OrderStatus, PaymentStatus, User, UserRole

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple"


def _make_staff(**overrides) -> User:
    defaults = dict(
        email="manager@example.test", name="Manager", role=UserRole.MANAGER,
        password_hash=hash_password(PASSWORD), must_change_password=False,
    )
    defaults.update(overrides)
    return User.objects.create(**defaults)


def _login(client, email: str = "manager@example.test") -> None:
    resp = client.post(reverse("manage:login"), {"email": email, "password": PASSWORD})
    assert resp.status_code == 302


def _base_payload(dish, slot, trading_day, **overrides) -> dict:
    payload = {
        "action": "place_order",
        "date": trading_day.date.isoformat(),
        "customer_name": "Jane Customer",
        "customer_mobile": "0821234567",
        "note": "",
        "source": OrderSource.PHONE,
        "payment_method": "eft",
        "eft_mode": "hold",
        "eft_confirm_reason": "",
        "slot_id": str(slot.pk),
        "after_cutoff_reason": "",
        f"qty_{dish.pk}": "2",
    }
    payload.update(overrides)
    return payload


class TestAssistedOrderEntry:
    def test_anonymous_redirected_to_login(self, client) -> None:
        resp = client.get(reverse("manage:assisted_order_new"))
        assert resp.status_code == 302

    def test_form_renders_the_days_dishes_and_slots(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        resp = client.get(
            reverse("manage:assisted_order_new"), {"date": trading_day.date.isoformat()},
        )
        assert resp.status_code == 200
        # `dish.name` contains "&", HTML-escaped on render — check a
        # substring that survives escaping unchanged.
        assert b"Chicken Curry" in resp.content
        assert f'value="{slot.pk}"'.encode() in resp.content

    def test_creates_a_real_order_via_reserve_same_as_web_checkout(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        resp = client.post(
            reverse("manage:assisted_order_new"), _base_payload(dish, slot, trading_day),
        )
        assert resp.status_code == 302

        order = Order.objects.get(customer_mobile_snapshot="+27821234567")
        assert order.source == OrderSource.PHONE
        assert order.status == OrderStatus.AWAITING_EFT
        assert order.created_by_user is not None
        assert order.created_by_user.email == "manager@example.test"
        assert order.lines.get().quantity == 2

    def test_capacity_parity_assisted_order_counts_against_the_same_slot_cap_as_web(
        self, client, biz_settings, trading_day, dish,
    ) -> None:
        """§20's own acceptance line this test stands in for: an
        assisted order and a web checkout draw from the *same* slot
        capacity — `reserve()` is the one shared §8.3 transaction, not
        two parallel implementations that could drift.
        """
        tiny_slot = trading_day.slots.create(
            start_at=dt.time(17, 0), end_at=dt.time(17, 15), capacity=1,
        )
        _make_staff()
        _login(client)

        resp = client.post(
            reverse("manage:assisted_order_new"),
            _base_payload(dish, tiny_slot, trading_day, slot_id=str(tiny_slot.pk)),
        )
        assert resp.status_code == 302
        assert Order.objects.filter(slot=tiny_slot).count() == 1

        # A second assisted order against the now-full slot is refused
        # with the exact same capacity ceiling web checkout would hit.
        resp2 = client.post(
            reverse("manage:assisted_order_new"),
            _base_payload(
                dish, tiny_slot, trading_day, slot_id=str(tiny_slot.pk),
                customer_mobile="0829999999",
            ),
        )
        assert resp2.status_code == 200  # re-rendered with an error, not redirected
        assert Order.objects.filter(slot=tiny_slot).count() == 1
        assert b"full" in resp2.content.lower()

    def test_eft_mode_payment_review_customer_says_paid_no_reason_needed(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        resp = client.post(
            reverse("manage:assisted_order_new"),
            _base_payload(dish, slot, trading_day, eft_mode="payment_review"),
        )
        assert resp.status_code == 302
        order = Order.objects.get(customer_mobile_snapshot="+27821234567")
        assert order.status == OrderStatus.PAYMENT_REVIEW

    def test_eft_mode_confirmed_prep_requires_a_reason(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        resp = client.post(
            reverse("manage:assisted_order_new"),
            _base_payload(dish, slot, trading_day, eft_mode="confirmed_prep"),
        )
        assert resp.status_code == 200
        assert Order.objects.filter(customer_mobile_snapshot="+27821234567").exists() is False

    def test_eft_mode_confirmed_prep_with_reason_counts_as_verify_eft(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        resp = client.post(
            reverse("manage:assisted_order_new"),
            _base_payload(
                dish, slot, trading_day,
                eft_mode="confirmed_prep", eft_confirm_reason="Saw the funds in the bank app",
            ),
        )
        assert resp.status_code == 302
        order = Order.objects.get(customer_mobile_snapshot="+27821234567")
        assert order.status == OrderStatus.CONFIRMED_PREP
        assert order.payment.status == PaymentStatus.VERIFIED
        event = order.events.get(action="verify_eft")
        assert event.actor_kind == ActorKind.STAFF
        assert event.payload["reason"] == "Saw the funds in the bank app"

    def test_cash_assisted_lands_in_cash_request_same_as_web(
        self, client, biz_settings, dish,
    ) -> None:
        # Cash requires same-day collection by default (M7's own rule,
        # `cash_same_day_only`) — build a trading day for real "today",
        # same reasoning test_cash_requests.py's own E2E test uses.
        from core.models import TradingDay
        from core.tz import now_sast

        today = now_sast().date()
        td = TradingDay.objects.create(
            date=today, is_open=True, window_start=dt.time(16, 0), window_end=dt.time(18, 0),
            cutoff_time=dt.time(23, 59), daily_order_cap=50,
        )
        cash_slot = td.slots.create(start_at=dt.time(16, 0), end_at=dt.time(16, 15), capacity=5)

        # Any same-day assisted order needs D-11's own permission,
        # independent of payment method — see `check_after_cutoff_permission`.
        biz_settings.assisted_after_cutoff_enabled = True
        biz_settings.save(update_fields=["assisted_after_cutoff_enabled"])

        _make_staff()
        _login(client)
        resp = client.post(
            reverse("manage:assisted_order_new"),
            _base_payload(
                dish, cash_slot, td, payment_method="cash",
                after_cutoff_reason="Phoned in for today",
            ),
        )
        assert resp.status_code == 302
        order = Order.objects.get(customer_mobile_snapshot="+27821234567")
        assert order.status == OrderStatus.CASH_REQUEST
        assert order.payment_method == "cash"


class TestAssistedOrderAfterCutoff:
    """D-11: a same-day assisted order needs `assisted_after_cutoff_enabled`
    plus a mandatory reason — enforced by `core.capacity.reserve()`
    itself (structural parity, not re-implemented in the view)."""

    def test_disabled_by_default_shows_the_capacity_error(
        self, client, biz_settings, dish,
    ) -> None:
        from core.tz import now_sast

        today = now_sast().date()
        from core.models import TradingDay

        td = TradingDay.objects.create(
            date=today, is_open=True, window_start=dt.time(16, 0), window_end=dt.time(18, 0),
            cutoff_time=dt.time(10, 0), daily_order_cap=100,
        )
        slot = td.slots.create(start_at=dt.time(16, 0), end_at=dt.time(16, 15), capacity=13)
        _make_staff()
        _login(client)

        resp = client.post(
            reverse("manage:assisted_order_new"),
            _base_payload(dish, slot, td, after_cutoff_reason="phoned in"),
        )
        assert resp.status_code == 200
        assert Order.objects.filter(customer_mobile_snapshot="+27821234567").exists() is False
        assert b"after-cut-off" in resp.content.lower() or b"disabled" in resp.content.lower()

    def test_reason_required_when_enabled(self, client, biz_settings, dish) -> None:
        from core.models import TradingDay
        from core.tz import now_sast

        biz_settings.assisted_after_cutoff_enabled = True
        biz_settings.save(update_fields=["assisted_after_cutoff_enabled"])

        today = now_sast().date()
        td = TradingDay.objects.create(
            date=today, is_open=True, window_start=dt.time(16, 0), window_end=dt.time(18, 0),
            cutoff_time=dt.time(10, 0), daily_order_cap=100,
        )
        slot = td.slots.create(start_at=dt.time(16, 0), end_at=dt.time(16, 15), capacity=13)
        _make_staff()
        _login(client)

        resp = client.post(
            reverse("manage:assisted_order_new"),
            _base_payload(dish, slot, td, after_cutoff_reason=""),
        )
        assert resp.status_code == 200
        assert Order.objects.filter(customer_mobile_snapshot="+27821234567").exists() is False

    def test_succeeds_when_enabled_with_reason(self, client, biz_settings, dish) -> None:
        from core.models import TradingDay
        from core.tz import now_sast

        biz_settings.assisted_after_cutoff_enabled = True
        biz_settings.save(update_fields=["assisted_after_cutoff_enabled"])

        today = now_sast().date()
        td = TradingDay.objects.create(
            date=today, is_open=True, window_start=dt.time(16, 0), window_end=dt.time(18, 0),
            cutoff_time=dt.time(10, 0), daily_order_cap=100,
        )
        slot = td.slots.create(start_at=dt.time(16, 0), end_at=dt.time(16, 15), capacity=13)
        _make_staff()
        _login(client)

        resp = client.post(
            reverse("manage:assisted_order_new"),
            _base_payload(dish, slot, td, after_cutoff_reason="Phoned in, taking the risk"),
        )
        assert resp.status_code == 302
        order = Order.objects.get(customer_mobile_snapshot="+27821234567")
        assert order.after_cutoff_reason == "Phoned in, taking the risk"
