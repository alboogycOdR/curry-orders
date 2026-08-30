"""Integration test for the order-status page's EFT hold countdown
(spec §11.7). Flagged by the user on the live site: an order already in
`payment_review` (proof uploaded) still showed a live "Pay within X:XX"
countdown ticking toward its original 30-minute hold deadline -- never
actually at risk of expiring (`core.eft.expire_holds` only ever touches
`awaiting_eft`), but genuinely misleading copy for a customer who has
already paid and uploaded proof.
"""
from __future__ import annotations

import datetime as dt

import pytest
from django.urls import reverse

from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.eft import record_proof_upload
from core.tz import now_sast

pytestmark = pytest.mark.django_db

NOW = dt.datetime(2026, 8, 31, 6, 0, tzinfo=dt.UTC)


def _eft_order(dish, slot, biz_settings, **overrides):
    defaults = dict(
        trading_day_date=dt.date(2026, 9, 1), slot_id=slot.pk, payment_method="eft",
        customer_name="Jane Customer", customer_mobile_e164="+27821234567",
        lines=[CheckoutLine(dish_id=dish.pk, quantity=1)], now=NOW,
    )
    defaults.update(overrides)
    return reserve(ReservationRequest(**defaults), biz_settings)


class TestEftHoldCountdown:
    def test_awaiting_eft_order_carries_the_countdown_deadline(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = _eft_order(dish, slot, biz_settings)
        resp = client.get(reverse("public:order_status", args=[order.public_token]))
        content = resp.content.decode()
        assert 'id="os-eft-panel"' in content
        assert "data-hold-expires-at=" in content

    def test_payment_review_order_drops_the_countdown_deadline(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = _eft_order(dish, slot, biz_settings)
        record_proof_upload(
            order, storage_key="p.jpg", mime_type="image/jpeg", byte_size=1,
            sha256=b"\x00" * 32, now=NOW,
        )
        resp = client.get(reverse("public:order_status", args=[order.public_token]))
        content = resp.content.decode()
        assert "Your proof is with us" in content
        # The order's own hold_expires_at is still a real (past) DB value
        # at this point -- the point is the *template* no longer renders
        # it into the countdown's data attribute, so eft.js has nothing
        # to tick down toward.
        assert "data-hold-expires-at=" not in content


class TestCopyShareLink:
    """Spec §13's "Order created" row: On-screen + token URL +
    Copy/Share — the bookmarkable order-status page itself carries the
    same button as checkout.html's confirmation panel (share-link.js),
    so a customer returning to it later can still re-share it.
    """

    def test_share_button_present_on_the_order_status_page(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = _eft_order(dish, slot, biz_settings)
        resp = client.get(reverse("public:order_status", args=[order.public_token]))
        content = resp.content.decode()
        assert 'id="os-share-link"' in content
        assert 'id="os-share-fallback"' in content
        assert 'id="os-share-input"' in content
