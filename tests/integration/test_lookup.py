"""Integration tests for §11.10's order lookup (`public/views.py::lookup`,
`/lookup/`) — throttle (10/hour/IP, 10/hour/order number, reusing M7's
`throttle_events` table via `core.lookup`), the 24h httpOnly cookie, and
the generic-failure-message rule (no account-enumeration leak).
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from core import lookup as lookup_service
from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.models import ThrottleEvent

pytestmark = pytest.mark.django_db


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


class TestLookupView:
    def test_get_renders_the_form(self, client) -> None:
        resp = client.get(reverse("public:lookup"))
        assert resp.status_code == 200

    def test_correct_order_number_and_mobile_redirects_and_sets_cookie(
        self, client, an_order,
    ) -> None:
        resp = client.post(reverse("public:lookup"), {
            "order_number": an_order.order_number, "mobile": "0821234567",
        })
        assert resp.status_code == 302
        assert resp.url == reverse("public:order_status", args=[an_order.public_token])
        cookie_name = f"order_auth_{an_order.public_token}"
        assert cookie_name in resp.cookies
        assert resp.cookies[cookie_name]["httponly"]
        assert resp.cookies[cookie_name]["max-age"] == 24 * 60 * 60

    def test_order_number_is_case_insensitive(self, client, an_order) -> None:
        resp = client.post(reverse("public:lookup"), {
            "order_number": an_order.order_number.lower(), "mobile": "0821234567",
        })
        assert resp.status_code == 302

    def test_mobile_matched_on_last_nine_digits_any_format(self, client, an_order) -> None:
        resp = client.post(reverse("public:lookup"), {
            "order_number": an_order.order_number, "mobile": "+27 82 123 4567",
        })
        assert resp.status_code == 302

    def test_wrong_mobile_shows_generic_message(self, client, an_order) -> None:
        resp = client.post(reverse("public:lookup"), {
            "order_number": an_order.order_number, "mobile": "0829999999",
        })
        assert resp.status_code == 200
        assert b"couldn" in resp.content.lower()

    def test_unknown_order_number_shows_the_same_generic_message(
        self, client, biz_settings,
    ) -> None:
        resp = client.post(reverse("public:lookup"), {
            "order_number": "CT-990101-9999", "mobile": "0821234567",
        })
        assert resp.status_code == 200
        assert b"couldn" in resp.content.lower()

    def test_no_account_enumeration_same_message_both_ways(self, client, an_order) -> None:
        # Page echoes the submitted order number back into the form
        # field, so compare the rendered error paragraph only, not the
        # whole page (which would otherwise legitimately differ).
        import re

        def _error_text(resp) -> bytes:
            match = re.search(rb'<p class="lk-error">(.*?)</p>', resp.content)
            return match.group(1) if match else b""

        wrong_mobile = client.post(reverse("public:lookup"), {
            "order_number": an_order.order_number, "mobile": "0829999999",
        })
        unknown_order = client.post(reverse("public:lookup"), {
            "order_number": "CT-990101-9999", "mobile": "0821234567",
        })
        assert _error_text(wrong_mobile) == _error_text(unknown_order)
        assert _error_text(wrong_mobile)


class TestLookupThrottle:
    def test_throttled_past_ten_attempts_per_ip(self, client, an_order) -> None:
        for _ in range(10):
            ThrottleEvent.objects.create(scope=lookup_service.LOOKUP_IP_SCOPE, key="127.0.0.1")
        resp = client.post(reverse("public:lookup"), {
            "order_number": an_order.order_number, "mobile": "0821234567",
        })
        assert resp.status_code == 200
        # §11.10's own "failures return a generic message" applies to a
        # throttled attempt too — same wording as a wrong mobile/unknown
        # order, not a distinct "you're throttled" tell.
        assert b"couldn" in resp.content.lower()
        # A throttled attempt is never allowed to succeed even with the
        # right answer — no redirect happened above.
        assert "Location" not in resp

    def test_throttled_past_ten_attempts_per_order_number(self, client, an_order) -> None:
        for _ in range(10):
            ThrottleEvent.objects.create(
                scope=lookup_service.LOOKUP_ORDER_SCOPE, key=an_order.order_number,
            )
        resp = client.post(reverse("public:lookup"), {
            "order_number": an_order.order_number, "mobile": "0821234567",
        })
        assert resp.status_code == 200
        assert b"couldn" in resp.content.lower()

    def test_a_failed_attempt_is_recorded_against_both_scopes(self, client, an_order) -> None:
        client.post(reverse("public:lookup"), {
            "order_number": an_order.order_number, "mobile": "0829999999",
        })
        assert ThrottleEvent.objects.filter(scope=lookup_service.LOOKUP_IP_SCOPE).exists()
        assert ThrottleEvent.objects.filter(
            scope=lookup_service.LOOKUP_ORDER_SCOPE, key=an_order.order_number,
        ).exists()


class TestLookupServiceUnit:
    def test_find_order_normalises_mobile_and_order_number(self, an_order) -> None:
        assert lookup_service.find_order(an_order.order_number.lower(), "082 123 4567") is not None

    def test_last9_digits(self) -> None:
        assert lookup_service.last9_digits("+27 82 123 4567") == "821234567"
        assert lookup_service.last9_digits("0821234567") == "821234567"
