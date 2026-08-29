"""Integration tests for POST /api/checkout (spec §11.6, §17.3)."""
from __future__ import annotations

import json

import pytest
from django.test import Client

from core.models import IdempotencyKey, Order

pytestmark = pytest.mark.django_db

URL = "/api/checkout"


def _payload(dish, slot, **overrides) -> dict:
    body = {
        "name": "Jane Customer",
        "mobile": "0821234567",
        "note": "",
        "date": "2026-09-01",
        "slot_id": slot.pk,
        "payment_method": "eft",
        "lines": [{"dish_id": dish.pk, "quantity": 1, "option_value_ids": []}],
        "accept_policies": True,
    }
    body.update(overrides)
    return body


def _post(client, payload, key="idem-key-1"):
    return client.post(
        URL, data=json.dumps(payload), content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


class TestValidation:
    def test_missing_idempotency_key_is_400(self, client, trading_day, slot, dish) -> None:
        body = json.dumps(_payload(dish, slot))
        resp = client.post(URL, data=body, content_type="application/json")
        assert resp.status_code == 400
        assert resp.json()["error"] == "validation_error"

    def test_malformed_json_is_400(self, client) -> None:
        resp = client.post(
            URL, data="not json", content_type="application/json", HTTP_IDEMPOTENCY_KEY="k1"
        )
        assert resp.status_code == 400

    def test_missing_name_is_400_with_field(self, client, trading_day, slot, dish) -> None:
        resp = _post(client, _payload(dish, slot, name=""))
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"
        assert "name" in body["fields"]

    def test_invalid_mobile_is_400(self, client, trading_day, slot, dish) -> None:
        resp = _post(client, _payload(dish, slot, mobile="12345"))
        assert resp.status_code == 400
        assert "mobile" in resp.json()["fields"]

    def test_note_too_long_is_400(self, client, trading_day, slot, dish) -> None:
        resp = _post(client, _payload(dish, slot, note="x" * 201))
        assert resp.status_code == 400
        assert "note" in resp.json()["fields"]

    def test_missing_accept_policies_is_400(self, client, trading_day, slot, dish) -> None:
        resp = _post(client, _payload(dish, slot, accept_policies=False))
        assert resp.status_code == 400
        assert "accept_policies" in resp.json()["fields"]

    def test_empty_lines_is_400(self, client, trading_day, slot, dish) -> None:
        resp = _post(client, _payload(dish, slot, lines=[]))
        assert resp.status_code == 400
        assert "lines" in resp.json()["fields"]

    def test_quantity_out_of_range_is_400(self, client, trading_day, slot, dish) -> None:
        line = {"dish_id": dish.pk, "quantity": 21, "option_value_ids": []}
        payload = _payload(dish, slot, lines=[line])
        resp = _post(client, payload)
        assert resp.status_code == 400
        assert "lines" in resp.json()["fields"]

    def test_bad_payment_method_is_400(self, client, trading_day, slot, dish) -> None:
        resp = _post(client, _payload(dish, slot, payment_method="bitcoin"))
        assert resp.status_code == 400
        assert "payment_method" in resp.json()["fields"]

    def test_get_not_allowed(self, client) -> None:
        resp = client.get(URL)
        assert resp.status_code == 405


class TestHappyPath:
    def test_creates_order_and_returns_201(
        self, client, trading_day, slot, dish, biz_settings
    ) -> None:
        resp = _post(client, _payload(dish, slot))
        assert resp.status_code == 201
        body = resp.json()
        assert body["order_number"] == "CT-260901-0001"
        assert body["status"] == "awaiting_eft"
        assert Order.objects.filter(order_number=body["order_number"]).exists()

    def test_records_idempotency_key(self, client, trading_day, slot, dish, biz_settings) -> None:
        _post(client, _payload(dish, slot), key="my-key")
        record = IdempotencyKey.objects.get(pk="my-key")
        assert record.response_status == 201
        assert record.order is not None

    def test_mobile_accepted_in_any_valid_shape(
        self, client, trading_day, slot, dish, biz_settings
    ) -> None:
        resp = _post(client, _payload(dish, slot, mobile="+27821234567"))
        assert resp.status_code == 201
        assert Order.objects.get().customer_mobile_snapshot == "+27821234567"


class TestIdempotency:
    def test_same_key_same_body_returns_cached_order(
        self, client, trading_day, slot, dish, biz_settings
    ) -> None:
        payload = _payload(dish, slot)
        first = _post(client, payload, key="repeat-key")
        second = _post(client, payload, key="repeat-key")
        assert first.status_code == second.status_code == 201
        assert first.json() == second.json()
        assert Order.objects.count() == 1  # not created twice

    def test_same_key_different_body_is_409(
        self, client, trading_day, slot, dish, biz_settings
    ) -> None:
        _post(client, _payload(dish, slot, note="first"), key="reused-key")
        resp = _post(client, _payload(dish, slot, note="different"), key="reused-key")
        assert resp.status_code == 409
        assert resp.json()["error"] == "idempotency_conflict"

    def test_different_keys_create_separate_orders(
        self, client, trading_day, slot, dish, biz_settings
    ) -> None:
        second_slot_payload = _payload(dish, slot)
        _post(client, second_slot_payload, key="key-a")
        _post(client, second_slot_payload, key="key-b")
        assert Order.objects.count() == 2


class TestCapacityFailures:
    def test_slot_full_is_422(self, client, trading_day, slot, dish, biz_settings) -> None:
        slot.capacity = 0
        slot.save(update_fields=["capacity"])
        resp = _post(client, _payload(dish, slot))
        assert resp.status_code == 422
        assert resp.json()["error"] == "slot_full"

    def test_day_closed_is_422(self, client, trading_day, slot, dish, biz_settings) -> None:
        trading_day.is_open = False
        trading_day.save(update_fields=["is_open"])
        resp = _post(client, _payload(dish, slot))
        assert resp.status_code == 422
        assert resp.json()["error"] == "day_closed"

    def test_no_order_created_on_capacity_failure(
        self, client, trading_day, slot, dish, biz_settings
    ) -> None:
        slot.capacity = 0
        slot.save(update_fields=["capacity"])
        _post(client, _payload(dish, slot))
        assert Order.objects.count() == 0
        assert not IdempotencyKey.objects.exists()


class TestCsrf:
    def test_missing_csrf_token_is_forbidden(self, trading_day, slot, dish, biz_settings) -> None:
        strict_client = Client(enforce_csrf_checks=True)
        resp = strict_client.post(
            URL, data=json.dumps(_payload(dish, slot)), content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="k1",
        )
        assert resp.status_code == 403
