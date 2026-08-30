"""Integration tests for §12.2's inbox (`staff/views.py::inbox`,
`/manage/`, the staff landing page) — section grouping, and the
assign/reinstate row actions.
"""
from __future__ import annotations

import datetime as dt

import pytest
from django.urls import reverse

from core.auth import hash_password
from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.models import Order, OrderSource, OrderStatus, User, UserRole
from core.transitions import Actor, apply
from core.tz import now_sast

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


def _req(dish, slot, trading_day, **overrides) -> ReservationRequest:
    defaults = dict(
        trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
        customer_name="Jane Customer", customer_mobile_e164="+27821234567",
        lines=[CheckoutLine(dish_id=dish.pk, quantity=1)],
    )
    defaults.update(overrides)
    return ReservationRequest(**defaults)


class TestInboxSections:
    def test_anonymous_redirected_to_login(self, client) -> None:
        resp = client.get(reverse("manage:inbox"))
        assert resp.status_code == 302

    def test_login_lands_on_the_inbox_by_default(self, client) -> None:
        _make_staff()
        resp = client.post(
            reverse("manage:login"), {"email": "manager@example.test", "password": PASSWORD},
        )
        assert resp.url == reverse("manage:inbox")

    def test_cash_request_appears_in_cash_section(
        self, client, biz_settings, dish,
    ) -> None:
        from core.models import TradingDay

        today = now_sast().date()
        td = TradingDay.objects.create(
            date=today, is_open=True, window_start=dt.time(16, 0), window_end=dt.time(18, 0),
            cutoff_time=dt.time(23, 59), daily_order_cap=50,
        )
        cash_slot = td.slots.create(start_at=dt.time(16, 0), end_at=dt.time(16, 15), capacity=5)
        order = reserve(_req(dish, cash_slot, td, payment_method="cash"), biz_settings)
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:inbox"))
        assert order.order_number.encode() in resp.content

    def test_hold_lapsed_order_appears(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = reserve(_req(dish, slot, trading_day), biz_settings)
        order.hold_expires_at = now_sast() - dt.timedelta(minutes=5)
        order.save(update_fields=["hold_expires_at"])
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:inbox"))
        assert order.order_number.encode() in resp.content

    def test_sla_breached_payment_review_order_appears(
        self, client, biz_settings, trading_day, slot, dish, staff_user,
    ) -> None:
        order = reserve(_req(dish, slot, trading_day), biz_settings)
        order = apply(
            order, "mark_payment_review", Actor("staff", staff_user), OrderStatus.AWAITING_EFT,
        )
        sla_minutes = biz_settings.payment_review_sla_minutes
        Order.objects.filter(pk=order.pk).update(
            created_at=now_sast() - dt.timedelta(minutes=sla_minutes + 5),
        )
        _make_staff(email="manager2@example.test")
        _login(client, "manager2@example.test")
        resp = client.get(reverse("manage:inbox"))
        assert order.order_number.encode() in resp.content

    def test_order_with_a_note_appears(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = reserve(_req(dish, slot, trading_day, note="Extra spicy please"), biz_settings)
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:inbox"))
        assert order.order_number.encode() in resp.content

    def test_assisted_order_appears_in_recent_assisted(
        self, client, biz_settings, trading_day, slot, dish, staff_user,
    ) -> None:
        order = reserve(
            _req(
                dish, slot, trading_day, source=OrderSource.PHONE,
                created_by_user=staff_user, is_staff_assisted=True,
            ),
            biz_settings,
        )
        _make_staff(email="logged-in-manager@example.test")
        _login(client, "logged-in-manager@example.test")
        resp = client.get(reverse("manage:inbox"))
        assert order.order_number.encode() in resp.content

    def test_website_order_does_not_appear_in_recent_assisted(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = reserve(_req(dish, slot, trading_day), biz_settings)
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:inbox"))
        assert b"No assisted orders yet." in resp.content
        assert order.source == OrderSource.WEBSITE

    def test_recently_expired_order_appears_with_reinstate_action(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = reserve(_req(dish, slot, trading_day), biz_settings)
        Order.objects.filter(pk=order.pk).update(
            status=OrderStatus.PAYMENT_EXPIRED, updated_at=now_sast(),
        )
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:inbox"))
        assert order.order_number.encode() in resp.content
        assert b'data-action="reinstate"' in resp.content

    def test_empty_inbox_shows_empty_states(self, client, biz_settings) -> None:
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:inbox"))
        assert resp.status_code == 200
        assert b"No cash requests waiting." in resp.content


class TestInboxAssign:
    def test_assign_to_me_then_unassign(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        import json

        order = reserve(_req(dish, slot, trading_day), biz_settings)
        _make_staff()
        _login(client)

        resp = client.post(
            reverse("manage:api_assign_order", args=[order.pk]),
            data=json.dumps({}), content_type="application/json",
        )
        assert resp.status_code == 200
        order.refresh_from_db()
        assert order.assigned_user.email == "manager@example.test"

        resp2 = client.post(
            reverse("manage:api_assign_order", args=[order.pk]),
            data=json.dumps({}), content_type="application/json",
        )
        assert resp2.status_code == 200
        order.refresh_from_db()
        assert order.assigned_user is None
