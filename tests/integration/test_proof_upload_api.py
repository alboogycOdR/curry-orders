"""Integration tests for POST /api/orders/:token/proof (spec §17.3,
milestone 4). Orders come through the real `core.capacity.reserve()`
transaction, same as test_eft.py.
"""
from __future__ import annotations

import datetime as dt

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.models import Order, OrderStatus, ThrottleEvent

pytestmark = pytest.mark.django_db

NOW = dt.datetime(2026, 8, 31, 6, 0, tzinfo=dt.UTC)

_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64


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


@pytest.fixture
def eft_order(biz_settings, trading_day, slot, dish):
    return reserve(_eft_req(dish, slot), biz_settings)


def _url(order) -> str:
    return f"/api/orders/{order.public_token}/proof"


def _upload(client, order, *, name="proof.jpg", content=_JPEG_BYTES, content_type="image/jpeg"):
    file = SimpleUploadedFile(name, content, content_type=content_type)
    return client.post(_url(order), data={"file": file})


class TestHappyPath:
    def test_valid_jpeg_moves_order_to_payment_review(self, client, eft_order) -> None:
        resp = _upload(client, eft_order)
        assert resp.status_code == 200
        assert resp.json() == {"status": "payment_review"}
        eft_order.refresh_from_db()
        assert eft_order.status == OrderStatus.PAYMENT_REVIEW
        assert eft_order.payment.current_proof_media is not None

    def test_a_real_pdf_is_accepted(self, client, eft_order) -> None:
        resp = _upload(
            client, eft_order, name="proof.pdf",
            content=b"%PDF-1.4\n" + b"\x00" * 64, content_type="application/pdf",
        )
        assert resp.status_code == 200
        eft_order.refresh_from_db()
        assert eft_order.payment.current_proof_media.mime_type == "application/pdf"


class TestValidation:
    def test_missing_file_is_400_upload_invalid(self, client, eft_order) -> None:
        resp = client.post(_url(eft_order), data={})
        assert resp.status_code == 400
        assert resp.json()["error"] == "upload_invalid"

    def test_wrong_content_masquerading_as_jpeg_is_rejected(self, client, eft_order) -> None:
        resp = _upload(client, eft_order, content=b"not a real jpeg at all")
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "upload_invalid"
        assert body["detail"] == "type"

    def test_oversized_file_is_rejected(self, client, eft_order) -> None:
        oversized = _JPEG_BYTES + b"\x00" * (8 * 1024 * 1024)
        resp = _upload(client, eft_order, content=oversized)
        assert resp.status_code == 400
        assert resp.json()["detail"] == "size"

    def test_unknown_token_is_404(self, client) -> None:
        file = SimpleUploadedFile("proof.jpg", _JPEG_BYTES, content_type="image/jpeg")
        resp = client.post("/api/orders/does-not-exist/proof", data={"file": file})
        assert resp.status_code == 404


class TestIllegalTransition:
    def test_a_collected_order_refuses_a_proof(self, client, eft_order) -> None:
        eft_order.status = OrderStatus.COLLECTED
        eft_order.save(update_fields=["status"])
        resp = _upload(client, eft_order)
        assert resp.status_code == 409
        assert resp.json()["error"] == "illegal_transition"


class TestThrottle:
    def test_sixth_attempt_in_an_hour_is_throttled(self, client, eft_order) -> None:
        ThrottleEvent.objects.bulk_create([
            ThrottleEvent(scope="proof_token", key=eft_order.public_token)
            for _ in range(5)
        ])
        resp = _upload(client, eft_order)
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"] == "throttled"
        assert body["retry_after_seconds"] == 3600
        # A validation failure never even reaches the throttle spend, but
        # a throttled request also shouldn't create an order side effect.
        eft_order.refresh_from_db()
        assert eft_order.status == OrderStatus.AWAITING_EFT

    def test_an_invalid_upload_does_not_spend_the_throttle_budget(self, client, eft_order) -> None:
        for _ in range(5):
            _upload(client, eft_order, content=b"garbage, not a real file")
        # All five were rejected as upload_invalid before ever recording
        # an attempt — a sixth real upload must still succeed.
        resp = _upload(client, eft_order)
        assert resp.status_code == 200


class TestCsrf:
    def test_missing_csrf_token_is_forbidden(self, eft_order) -> None:
        strict_client = Client(enforce_csrf_checks=True)
        resp = _upload(strict_client, eft_order)
        assert resp.status_code == 403


class TestNoLeakToOtherOrders:
    def test_uploading_against_one_order_does_not_touch_another(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order_a = reserve(_eft_req(dish, slot, customer_mobile_e164="+27821111111"), biz_settings)
        second_slot_start = dt.time(16, 15)
        from core.models import Slot

        slot_b = Slot.objects.create(
            trading_day=trading_day, start_at=second_slot_start, end_at=dt.time(16, 30), capacity=5,
        )
        order_b = reserve(_eft_req(dish, slot_b, customer_mobile_e164="+27822222222"), biz_settings)

        _upload(client, order_a)

        order_a.refresh_from_db()
        order_b.refresh_from_db()
        assert order_a.status == OrderStatus.PAYMENT_REVIEW
        assert order_b.status == OrderStatus.AWAITING_EFT
        assert Order.objects.get(pk=order_b.pk).payment.current_proof_media is None
