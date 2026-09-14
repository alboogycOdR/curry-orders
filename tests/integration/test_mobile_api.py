"""Integration tests for the Flutter Android app's JSON API
(docs/mobile/FLUTTER_APP_PLAN.md Phase 1, `public/urls_v1_api.py`,
`public/api.py`'s "Flutter app (Phase 1)" section).

Mounted only on the poster-variant urlconf (`config.urls_v2_root`), not
the default `config.urls` these tests would otherwise resolve against —
every test below opts into it via `pytest.mark.urls`. Session/CSRF
behaviour otherwise matches the web: Django's test `Client` skips CSRF
enforcement by default, same as every other POST test in this suite
(e.g. `test_customer_auth.py`), so these tests don't need to fetch
`csrf/` first — a real mobile client does (see `api.csrf_cookie`'s own
docstring).
"""
from __future__ import annotations

import json

import pytest
from django.urls import reverse

from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.models import Customer, OrderStatus, ThrottleEvent
from core.tz import now_sast

pytestmark = [pytest.mark.django_db, pytest.mark.urls("config.urls_v2_root")]


def _post_json(client, url_name, body: dict, **kwargs):
    return client.post(
        reverse(url_name), data=json.dumps(body), content_type="application/json", **kwargs
    )


@pytest.fixture
def an_order(biz_settings, trading_day, slot, dish):
    return reserve(
        ReservationRequest(
            trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
            customer_name="Jane Customer", customer_mobile_e164="+27821234567",
            lines=[CheckoutLine(dish_id=dish.pk, quantity=1)],
        ),
        biz_settings,
    )


class TestCsrfCookie:
    def test_sets_the_csrftoken_cookie(self, client, biz_settings) -> None:
        resp = client.get(reverse("api_v1:csrf"))
        assert resp.status_code == 200
        assert "csrftoken" in resp.cookies


class TestReorderJson:
    def test_only_a_collected_order_can_be_reordered(self, client, an_order) -> None:
        resp = client.get(reverse("api_v1:reorder", args=[an_order.public_token]))
        assert resp.status_code == 422
        assert resp.json()["error"] == "illegal_transition"

    def test_returns_current_price_lines_for_a_collected_order(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = reserve(
            ReservationRequest(
                trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
                customer_name="Jane Customer", customer_mobile_e164="+27821234567",
                lines=[CheckoutLine(dish_id=dish.pk, quantity=2)],
            ),
            biz_settings,
        )
        order.status = OrderStatus.COLLECTED
        order.collected_at = now_sast()
        order.save(update_fields=["status", "collected_at"])

        # Price went up after the order — reorder must quote today's price.
        dish.price_cents += 5000
        dish.save(update_fields=["price_cents"])

        resp = client.get(reverse("api_v1:reorder", args=[order.public_token]))
        assert resp.status_code == 200
        body = resp.json()
        (line,) = body["lines"]
        assert line["dish_id"] == dish.pk
        assert line["quantity"] == 2
        assert line["unit_price_cents"] == dish.price_cents
        assert body["dropped_dish_names"] == []

    def test_unknown_token_is_not_found(self, client, biz_settings) -> None:
        resp = client.get(reverse("api_v1:reorder", args=["nonexistent-token-123456"]))
        assert resp.status_code == 404


class TestOrderableDaysJson:
    def test_returns_the_orderable_day_list(self, client, biz_settings) -> None:
        resp = client.get(reverse("api_v1:days"))
        assert resp.status_code == 200
        days = resp.json()["days"]
        assert days
        assert set(days[0].keys()) == {"index", "iso", "dow", "dom", "long"}


class TestOrderStatusJson:
    def test_returns_order_fields(self, client, an_order) -> None:
        resp = client.get(reverse("api_v1:order_status", args=[an_order.public_token]))
        assert resp.status_code == 200
        body = resp.json()
        assert body["order_number"] == an_order.order_number
        assert body["public_token"] == an_order.public_token
        assert body["status"] == an_order.status
        assert body["lines"]
        # awaiting_eft — the EFT panel block should be present with bank fields.
        assert "eft" in body
        assert body["eft"]["reference"] == an_order.order_number

    def test_unknown_token_is_not_found(self, client, biz_settings) -> None:
        resp = client.get(reverse("api_v1:order_status", args=["does-not-exist"]))
        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"


class TestLookupJson:
    def test_correct_order_number_and_mobile_returns_the_order(self, client, an_order) -> None:
        body = {"order_number": an_order.order_number, "mobile": "0821234567"}
        resp = _post_json(client, "api_v1:lookup", body)
        assert resp.status_code == 200
        assert resp.json()["orders"][0]["order_number"] == an_order.order_number

    def test_wrong_mobile_returns_the_generic_not_found_message(self, client, an_order) -> None:
        body = {"order_number": an_order.order_number, "mobile": "0829999999"}
        resp = _post_json(client, "api_v1:lookup", body)
        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"

    def test_blank_order_number_without_a_session_requires_auth(self, client, biz_settings) -> None:
        resp = _post_json(client, "api_v1:lookup", {"mobile": "0821234567"})
        assert resp.status_code == 401
        assert resp.json()["error"] == "auth_required"

    def test_throttled_past_ten_attempts_per_ip(self, client, an_order) -> None:
        from core import lookup as lookup_service

        for _ in range(10):
            ThrottleEvent.objects.create(scope=lookup_service.LOOKUP_IP_SCOPE, key="127.0.0.1")
        body = {"order_number": an_order.order_number, "mobile": "0821234567"}
        resp = _post_json(client, "api_v1:lookup", body)
        assert resp.status_code == 429
        assert resp.json()["error"] == "throttled"


class TestAuthJson:
    def test_signup_then_login_then_account(self, client, biz_settings) -> None:
        resp = _post_json(
            client, "api_v1:signup",
            {"name": "A Customer", "mobile": "082 123 4567", "password": "password123"},
        )
        assert resp.status_code == 201
        customer = Customer.objects.get(mobile_e164="+27821234567")
        assert customer.password_hash

        account_resp = client.get(reverse("api_v1:account"))
        assert account_resp.status_code == 200
        assert account_resp.json()["full_name"] == "A Customer"

        logout_resp = client.post(reverse("api_v1:logout"))
        assert logout_resp.status_code == 200
        assert client.get(reverse("api_v1:account")).status_code == 401

        login_resp = _post_json(
            client, "api_v1:login", {"mobile": "082 123 4567", "password": "password123"},
        )
        assert login_resp.status_code == 200
        assert login_resp.json()["full_name"] == "A Customer"
        assert client.get(reverse("api_v1:account")).status_code == 200

    def test_login_rejects_bad_password(self, client, biz_settings) -> None:
        Customer.objects.create(
            full_name="A Customer", mobile_e164="+27821234567", password_hash="not-a-real-hash",
        )
        resp = _post_json(
            client, "api_v1:login", {"mobile": "082 123 4567", "password": "wrong-password"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "validation_error"

    def test_login_throttles_after_ten_failures_from_same_ip(self, client, biz_settings) -> None:
        for _ in range(10):
            ThrottleEvent.objects.create(scope="login_ip", key="127.0.0.1")
        resp = _post_json(
            client, "api_v1:login", {"mobile": "082 123 4567", "password": "whatever"},
        )
        assert resp.status_code == 429
        assert resp.json()["error"] == "throttled_login"

    def test_signup_refuses_to_claim_an_existing_guest_row(self, client, biz_settings) -> None:
        Customer.objects.create(
            full_name="Guest Orderer", mobile_e164="+27821234567", password_hash=None,
        )
        resp = _post_json(
            client, "api_v1:signup",
            {"name": "Attacker", "mobile": "082 123 4567", "password": "password123"},
        )
        assert resp.status_code == 400
        customer = Customer.objects.get(mobile_e164="+27821234567")
        assert customer.password_hash is None

    def test_account_requires_auth(self, client, biz_settings) -> None:
        resp = client.get(reverse("api_v1:account"))
        assert resp.status_code == 401
        assert resp.json()["error"] == "auth_required"


class TestAccountOrdersJson:
    def test_requires_auth(self, client, biz_settings) -> None:
        resp = client.get(reverse("api_v1:account_orders"))
        assert resp.status_code == 401

    def test_returns_the_signed_in_customers_own_orders(self, client, an_order) -> None:
        # reserve() (the `an_order` fixture) already created a guest
        # Customer row for this mobile — give it a password directly
        # rather than going through signup (which would refuse to claim
        # a pre-existing guest row, by design; see TestAuthJson above).
        from django.contrib.auth.hashers import make_password

        customer = Customer.objects.get(mobile_e164="+27821234567")
        customer.password_hash = make_password("password123")
        customer.save(update_fields=["password_hash"])

        login_resp = _post_json(
            client, "api_v1:login", {"mobile": "082 123 4567", "password": "password123"},
        )
        assert login_resp.status_code == 200

        resp = client.get(reverse("api_v1:account_orders"))
        assert resp.status_code == 200
        numbers = {o["order_number"] for o in resp.json()["orders"]}
        assert an_order.order_number in numbers
