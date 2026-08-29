"""Integration tests for the EFT payment queue: `staff/views.py`'s
`payments_queue` (§12.3, real `core.Order` rows) and `staff/api.py`'s
`manage:api_transition` endpoint (the real `core.transitions.apply()`
dispatcher, session-authed + CSRF).
"""
from __future__ import annotations

import datetime as dt
import json

import pytest
from django.test import Client
from django.urls import reverse

from core.auth import hash_password
from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.models import OrderStatus, User, UserRole

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple"
NOW = dt.datetime(2026, 8, 31, 6, 0, tzinfo=dt.UTC)


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


class TestPaymentsQueueView:
    def test_anonymous_redirected_to_login(self, client) -> None:
        resp = client.get(reverse("manage:payments"))
        assert resp.status_code == 302
        assert resp.url.startswith(reverse("manage:login"))

    def test_lists_only_awaiting_eft_and_payment_review(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)

        awaiting = reserve(_eft_req(dish, slot), biz_settings)
        second_slot = slot.trading_day.slots.create(
            start_at=dt.time(16, 15), end_at=dt.time(16, 30), capacity=5,
        )
        confirmed = reserve(
            _eft_req(dish, second_slot, customer_mobile_e164="+27829999999"), biz_settings,
        )
        confirmed.status = OrderStatus.CONFIRMED_PREP
        confirmed.save(update_fields=["status"])

        resp = client.get(reverse("manage:payments"))
        assert resp.status_code == 200
        assert awaiting.order_number.encode() in resp.content
        assert confirmed.order_number.encode() not in resp.content

    def test_empty_state(self, client) -> None:
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:payments"))
        assert resp.status_code == 200
        assert b"Nothing awaiting EFT payment" in resp.content


class TestTransitionApi:
    def _url(self, order) -> str:
        return reverse("manage:api_transition", args=[order.pk])

    def test_anonymous_redirected_to_login(self, biz_settings, trading_day, slot, dish) -> None:
        order = reserve(_eft_req(dish, slot), biz_settings)
        resp = Client().post(
            self._url(order),
            data=json.dumps({"action": "extend_hold", "expected_status": "awaiting_eft"}),
            content_type="application/json",
        )
        assert resp.status_code == 302
        assert resp.url.startswith(reverse("manage:login"))

    def test_verify_eft_via_the_endpoint(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        order = reserve(_eft_req(dish, slot), biz_settings)
        from core.eft import record_proof_upload

        record_proof_upload(
            order, storage_key="p.jpg", mime_type="image/jpeg", byte_size=1,
            sha256=b"\x00" * 32, now=NOW,
        )
        order.refresh_from_db()

        resp = client.post(
            self._url(order),
            data=json.dumps({"action": "verify_eft", "expected_status": "payment_review"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "confirmed_prep"
        order.refresh_from_db()
        assert order.status == OrderStatus.CONFIRMED_PREP
        event = order.events.get(action="verify_eft")
        assert event.actor_user_id == User.objects.get(email="manager@example.test").pk

    def test_stale_state_is_409(self, client, biz_settings, trading_day, slot, dish) -> None:
        _make_staff()
        _login(client)
        order = reserve(_eft_req(dish, slot), biz_settings)
        resp = client.post(
            self._url(order),
            data=json.dumps({"action": "reject_eft", "expected_status": "payment_review"}),
            content_type="application/json",
        )
        assert resp.status_code == 409
        assert resp.json()["error"] == "stale_state"
        assert resp.json()["current_status"] == "awaiting_eft"

    def test_reason_required_is_403(self, client, biz_settings, trading_day, slot, dish) -> None:
        _make_staff()
        _login(client)
        order = reserve(_eft_req(dish, slot), biz_settings)
        resp = client.post(
            self._url(order),
            data=json.dumps({"action": "verify_eft", "expected_status": "awaiting_eft"}),
            content_type="application/json",
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "reason_required"

    def test_unknown_order_is_404(self, client) -> None:
        _make_staff()
        _login(client)
        resp = client.post(
            reverse("manage:api_transition", args=[999999]),
            data=json.dumps({"action": "extend_hold", "expected_status": "awaiting_eft"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_malformed_json_is_400(self, client, biz_settings, trading_day, slot, dish) -> None:
        _make_staff()
        _login(client)
        order = reserve(_eft_req(dish, slot), biz_settings)
        resp = client.post(self._url(order), data="not json", content_type="application/json")
        assert resp.status_code == 400

    def test_missing_csrf_token_is_forbidden(self, biz_settings, trading_day, slot, dish) -> None:
        _make_staff()
        strict_client = Client(enforce_csrf_checks=True)
        # The login POST itself needs a real token under strict checking
        # (this custom staff auth isn't `Client.login()`-compatible — see
        # staff/sessions.py) — fetch the login page first to get one.
        login_page = strict_client.get(reverse("manage:login"))
        csrf_token = login_page.cookies["csrftoken"].value
        login_resp = strict_client.post(reverse("manage:login"), {
            "email": "manager@example.test", "password": PASSWORD,
            "csrfmiddlewaretoken": csrf_token,
        })
        assert login_resp.status_code == 302
        order = reserve(_eft_req(dish, slot), biz_settings)
        resp = strict_client.post(
            self._url(order),
            data=json.dumps({"action": "extend_hold", "expected_status": "awaiting_eft"}),
            content_type="application/json",
        )
        assert resp.status_code == 403
