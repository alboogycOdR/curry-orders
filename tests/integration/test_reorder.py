"""Integration tests for §11.11's reorder (`public/views.py::reorder`,
`/orders/:token/reorder/`) — a fresh cart from a collected order's own
lines, at current prices, with an archived/deactivated dish dropped and
listed in a notice.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.models import Dish, OrderStatus
from core.tz import now_sast

pytestmark = pytest.mark.django_db


def _make_order(biz_settings, trading_day, slot, dish, **line_overrides):
    order = reserve(
        ReservationRequest(
            trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
            customer_name="Jane Customer", customer_mobile_e164="+27821234567",
            lines=[CheckoutLine(dish_id=dish.pk, quantity=2, **line_overrides)],
        ),
        biz_settings,
    )
    order.status = OrderStatus.COLLECTED
    order.collected_at = now_sast()
    order.save(update_fields=["status", "collected_at"])
    return order


@pytest.fixture
def other_dish(db) -> Dish:
    return Dish.objects.create(
        slug="beef-bunny-chow", name="Beef Bunny Chow", price_cents=9500,
        category="Bunny Chow", is_active_on_menu=True,
    )


def _make_two_line_order(biz_settings, trading_day, slot, dish, other_dish):
    order = reserve(
        ReservationRequest(
            trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
            customer_name="Jane Customer", customer_mobile_e164="+27821234567",
            lines=[
                CheckoutLine(dish_id=dish.pk, quantity=1),
                CheckoutLine(dish_id=other_dish.pk, quantity=1),
            ],
        ),
        biz_settings,
    )
    order.status = OrderStatus.COLLECTED
    order.collected_at = now_sast()
    order.save(update_fields=["status", "collected_at"])
    return order


class TestReorder:
    def test_only_a_collected_order_can_be_reordered(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = reserve(
            ReservationRequest(
                trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
                customer_name="Jane", customer_mobile_e164="+27821234567",
                lines=[CheckoutLine(dish_id=dish.pk, quantity=1)],
            ),
            biz_settings,
        )
        resp = client.get(reverse("public:reorder", args=[order.public_token]), follow=True)
        assert resp.redirect_chain
        assert b"Only a collected order" in resp.content

    def test_no_longer_available_button_on_a_collected_order_status_page(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = _make_order(biz_settings, trading_day, slot, dish)
        resp = client.get(reverse("public:order_status", args=[order.public_token]))
        assert reverse("public:reorder", args=[order.public_token]).encode() in resp.content

    def test_seeds_a_cart_at_current_price_not_the_snapshot(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = _make_order(biz_settings, trading_day, slot, dish)
        # Dish got more expensive after the order was placed — the
        # reorder cart must use *today's* price, not the order line's
        # own unit_price_cents_snapshot.
        dish.price_cents = dish.price_cents + 5000
        dish.save(update_fields=["price_cents"])

        resp = client.get(reverse("public:reorder", args=[order.public_token]))
        assert resp.status_code == 200
        assert str(dish.price_cents).encode() in resp.content
        assert order.lines.get().unit_price_cents_snapshot != dish.price_cents

    def test_archived_dish_is_dropped_and_listed(
        self, client, biz_settings, trading_day, slot, dish, other_dish,
    ) -> None:
        order = _make_two_line_order(biz_settings, trading_day, slot, dish, other_dish)
        dish.archived_at = now_sast()
        dish.save(update_fields=["archived_at"])

        resp = client.get(reverse("public:reorder", args=[order.public_token]))
        assert resp.status_code == 200
        assert b"No longer available" in resp.content

    def test_deactivated_dish_is_dropped_and_listed(
        self, client, biz_settings, trading_day, slot, dish, other_dish,
    ) -> None:
        order = _make_two_line_order(biz_settings, trading_day, slot, dish, other_dish)
        dish.is_active_on_menu = False
        dish.save(update_fields=["is_active_on_menu"])

        resp = client.get(reverse("public:reorder", args=[order.public_token]))
        assert resp.status_code == 200
        assert b"No longer available" in resp.content

    def test_all_dishes_dropped_redirects_back_with_a_message(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = _make_order(biz_settings, trading_day, slot, dish)
        dish.archived_at = now_sast()
        dish.save(update_fields=["archived_at"])

        resp = client.get(reverse("public:reorder", args=[order.public_token]), follow=True)
        assert resp.redirect_chain
        assert resp.redirect_chain[-1][0] == reverse(
            "public:order_status", args=[order.public_token],
        )

    def test_unknown_token_404s(self, client) -> None:
        resp = client.get(reverse("public:reorder", args=["nonexistent-token-123456"]))
        assert resp.status_code == 404
