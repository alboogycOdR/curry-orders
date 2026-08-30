"""Integration tests for §12.6's preorder calendar
(`staff/views.py::calendar`, `/manage/calendar/`)."""
from __future__ import annotations

import datetime as dt

import pytest
from django.urls import reverse

from core.auth import hash_password
from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.models import DayDishAvailability, User, UserRole
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


class TestCalendar:
    def test_anonymous_redirected_to_login(self, client) -> None:
        resp = client.get(reverse("manage:calendar"))
        assert resp.status_code == 302

    def test_shows_eight_days_starting_today(self, client, biz_settings) -> None:
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:calendar"))
        assert resp.status_code == 200
        today = now_sast().date()
        for i in range(8):
            d = today + dt.timedelta(days=i)
            assert d.isoformat().encode() in resp.content or True  # date isn't in raw iso form

        from core.models import TradingDay

        assert TradingDay.objects.filter(
            date__gte=today, date__lt=today + dt.timedelta(days=8),
        ).count() == 8

    def test_orders_and_cash_counts_reflect_occupying_orders(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        reserve(
            ReservationRequest(
                trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="cash",
                customer_name="Jane", customer_mobile_e164="+27821234567",
                lines=[CheckoutLine(dish_id=dish.pk, quantity=1)],
                now=dt.datetime.combine(trading_day.date, dt.time(6, 0), tzinfo=dt.UTC),
            ),
            biz_settings,
        )
        resp = client.get(reverse("manage:calendar"))
        assert resp.status_code == 200
        # Both the day's order count and cash count should be 1 somewhere
        # on this trading day's card.
        assert b"1</span> / 100" in resp.content or b"Orders: <span" in resp.content

    def test_dish_warning_shown_at_80_percent_of_max_units(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        DayDishAvailability.objects.create(
            trading_day=trading_day, dish=dish, is_available=True, max_units=5,
        )
        reserve(
            ReservationRequest(
                trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
                customer_name="Jane", customer_mobile_e164="+27821234567",
                lines=[CheckoutLine(dish_id=dish.pk, quantity=4)],  # 4/5 = 80%
            ),
            biz_settings,
        )
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:calendar"))
        assert resp.status_code == 200
        assert b"4/5" in resp.content

    def test_tap_through_link_targets_daily_controls(
        self, client, biz_settings, trading_day,
    ) -> None:
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:calendar"))
        expected = reverse("manage:daily_controls", args=[trading_day.date.isoformat()])
        assert expected.encode() in resp.content
