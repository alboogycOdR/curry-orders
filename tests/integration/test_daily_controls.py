"""Integration tests for daily controls (spec §12.8, milestone 8 —
narrowed to this; the menu editor is a separate, deferred piece).
`staff/views.py::daily_controls`/`daily_controls_today` and
`staff/api.py::move_all_orders`.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest
from django.urls import reverse

from core.auth import hash_password
from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.menu import active_dishes
from core.models import DayDishAvailability, OrderStatus, User, UserRole

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


def _login(client, email: str = "manager@example.test") -> None:
    resp = client.post(reverse("manage:login"), {"email": email, "password": PASSWORD})
    assert resp.status_code == 302


def _base_form_data(trading_day, dish=None) -> dict:
    data = {
        "is_open": "on",
        "window_start": trading_day.window_start.strftime("%H:%M"),
        "window_end": trading_day.window_end.strftime("%H:%M"),
        "cutoff_time": trading_day.cutoff_time.strftime("%H:%M"),
        "daily_order_cap": str(trading_day.daily_order_cap),
        "notes_internal": "",
    }
    for s in trading_day.slots.all():
        data[f"slot_capacity_{s.pk}"] = str(s.capacity)
        if s.is_closed:
            data[f"slot_closed_{s.pk}"] = "on"
    for d in active_dishes():
        data[f"dish_available_{d.pk}"] = "on"
    return data


def _url(trading_day) -> str:
    return reverse("manage:daily_controls", args=[trading_day.date.isoformat()])


class TestDailyControlsView:
    def test_anonymous_redirected_to_login(self, trading_day) -> None:
        from django.test import Client

        resp = Client().get(_url(trading_day))
        assert resp.status_code == 302

    def test_manager_can_access_not_owner_only(self, client, trading_day) -> None:
        # §4's role table: daily controls is a Manager capability, not
        # owner-only (unlike settings/staff admin).
        _make_staff()
        _login(client)
        resp = client.get(_url(trading_day))
        assert resp.status_code == 200

    def test_renders_slots_and_active_dishes(self, client, trading_day, slot, dish) -> None:
        _make_staff()
        _login(client)
        resp = client.get(_url(trading_day))
        content = resp.content.decode()
        assert f"slot_capacity_{slot.pk}" in content
        assert f"dish_available_{dish.pk}" in content

    def test_today_redirect(self, client, biz_settings) -> None:
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:daily_controls_today"))
        assert resp.status_code == 302
        assert "/manage/days/" in resp.url

    def test_saves_day_level_fields(self, client, biz_settings, trading_day, slot, dish) -> None:
        _make_staff()
        _login(client)
        data = _base_form_data(trading_day)
        data["daily_order_cap"] = "42"
        data["notes_internal"] = "Owner on leave this week"
        resp = client.post(_url(trading_day), data)
        assert resp.status_code == 302
        trading_day.refresh_from_db()
        assert trading_day.daily_order_cap == 42
        assert trading_day.notes_internal == "Owner on leave this week"

    def test_slot_capacity_cannot_go_below_occupancy(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        reserve(
            ReservationRequest(
                trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
                customer_name="Jane", customer_mobile_e164="+27821234567",
                lines=[CheckoutLine(dish_id=dish.pk, quantity=1)], now=NOW,
            ),
            biz_settings,
        )
        data = _base_form_data(trading_day)
        data[f"slot_capacity_{slot.pk}"] = "0"
        resp = client.post(_url(trading_day), data)
        assert resp.status_code == 200  # re-rendered, not redirected
        assert b"below" in resp.content
        slot.refresh_from_db()
        assert slot.capacity != 0

    def test_closing_a_slot_with_occupying_orders_needs_confirmation(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        order = reserve(
            ReservationRequest(
                trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
                customer_name="Jane", customer_mobile_e164="+27821234567",
                lines=[CheckoutLine(dish_id=dish.pk, quantity=1)], now=NOW,
            ),
            biz_settings,
        )
        data = _base_form_data(trading_day)
        data[f"slot_closed_{slot.pk}"] = "on"

        resp = client.post(_url(trading_day), data)
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "This will affect orders" in content
        assert order.order_number in content
        slot.refresh_from_db()
        assert slot.is_closed is False  # not saved without confirmation

        data["confirm_close"] = "1"
        resp2 = client.post(_url(trading_day), data)
        assert resp2.status_code == 302
        slot.refresh_from_db()
        assert slot.is_closed is True  # order keeps its slot regardless
        order.refresh_from_db()
        assert order.slot_id == slot.pk

    def test_closing_the_day_with_occupying_orders_needs_confirmation(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        reserve(
            ReservationRequest(
                trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
                customer_name="Jane", customer_mobile_e164="+27821234567",
                lines=[CheckoutLine(dish_id=dish.pk, quantity=1)], now=NOW,
            ),
            biz_settings,
        )
        data = _base_form_data(trading_day)
        del data["is_open"]  # unchecked checkbox

        resp = client.post(_url(trading_day), data)
        assert "This will affect orders" in resp.content.decode()
        trading_day.refresh_from_db()
        assert trading_day.is_open is True

        data["confirm_close"] = "1"
        resp2 = client.post(_url(trading_day), data)
        assert resp2.status_code == 302
        trading_day.refresh_from_db()
        assert trading_day.is_open is False

    def test_sells_out_one_dish_without_touching_the_monthly_menu(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        # §20's own acceptance line.
        _make_staff()
        _login(client)
        data = _base_form_data(trading_day)
        del data[f"dish_available_{dish.pk}"]  # sell it out today only

        resp = client.post(_url(trading_day), data)
        assert resp.status_code == 302
        avail = DayDishAvailability.objects.get(trading_day=trading_day, dish=dish)
        assert avail.is_available is False
        dish.refresh_from_db()
        assert dish.is_active_on_menu is True  # monthly menu untouched

    def test_dish_max_units_saved(self, client, biz_settings, trading_day, slot, dish) -> None:
        _make_staff()
        _login(client)
        data = _base_form_data(trading_day)
        data[f"dish_max_units_{dish.pk}"] = "5"
        resp = client.post(_url(trading_day), data)
        assert resp.status_code == 302
        avail = DayDishAvailability.objects.get(trading_day=trading_day, dish=dish)
        assert avail.max_units == 5


class TestMoveAllOrders:
    def _url(self, trading_day, slot) -> str:
        return reverse(
            "manage:api_move_all_orders", args=[trading_day.date.isoformat(), slot.pk],
        )

    def test_moves_occupying_orders_to_the_target_slot(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        target_slot = trading_day.slots.create(
            start_at=dt.time(16, 15), end_at=dt.time(16, 30), capacity=5,
        )
        order = reserve(
            ReservationRequest(
                trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
                customer_name="Jane", customer_mobile_e164="+27821234567",
                lines=[CheckoutLine(dish_id=dish.pk, quantity=1)], now=NOW,
            ),
            biz_settings,
        )
        resp = client.post(
            self._url(trading_day, slot),
            data=json.dumps({"to_slot_id": target_slot.pk}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json() == {"moved": 1, "failures": []}
        order.refresh_from_db()
        assert order.slot_id == target_slot.pk
        assert order.status == OrderStatus.AWAITING_EFT  # unchanged, just relocated

    def test_reports_failures_without_losing_the_ones_that_moved(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        target_slot = trading_day.slots.create(
            start_at=dt.time(16, 15), end_at=dt.time(16, 30), capacity=1,
        )
        order_a = reserve(
            ReservationRequest(
                trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
                customer_name="Customer A", customer_mobile_e164="+27821111111",
                lines=[CheckoutLine(dish_id=dish.pk, quantity=1)], now=NOW,
            ),
            biz_settings,
        )
        order_b = reserve(
            ReservationRequest(
                trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
                customer_name="Customer B", customer_mobile_e164="+27822222222",
                lines=[CheckoutLine(dish_id=dish.pk, quantity=1)], now=NOW,
            ),
            biz_settings,
        )
        resp = client.post(
            self._url(trading_day, slot),
            data=json.dumps({"to_slot_id": target_slot.pk}),
            content_type="application/json",
        )
        body = resp.json()
        assert body["moved"] == 1
        assert len(body["failures"]) == 1
        order_a.refresh_from_db()
        order_b.refresh_from_db()
        moved_slots = {order_a.slot_id, order_b.slot_id}
        assert target_slot.pk in moved_slots
        assert slot.pk in moved_slots  # the one that couldn't fit stayed put

    def test_unknown_slot_is_404(self, client, trading_day) -> None:
        _make_staff()
        _login(client)
        resp = client.post(
            reverse(
                "manage:api_move_all_orders", args=[trading_day.date.isoformat(), 999999],
            ),
            data=json.dumps({"to_slot_id": 1}),
            content_type="application/json",
        )
        assert resp.status_code == 404
