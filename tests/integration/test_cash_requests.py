"""Integration tests for the cash path (spec §22 milestone 7): the
customer-facing cash checkout (already real since milestone 3's
`POST /api/checkout` and `core.capacity.reserve()`'s `check_cash`), and
the new staff-side cash requests queue (`staff/views.py::cash_requests`,
`staff/api.py`'s existing generic transition endpoint) — a full E2E from
checkout through accept, kitchen, and collection with a cash amount.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest
from django.urls import reverse

from core.auth import hash_password
from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.models import ActorKind, OrderStatus, PaymentStatus, User, UserRole
from core.transitions import Actor, apply

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple"
# Same calendar day as trading_day (cash_same_day_only defaults true),
# before the default 10:00 SAST cutoff.
SAME_DAY_BEFORE_CUTOFF = dt.datetime(2026, 9, 1, 6, 0, tzinfo=dt.UTC)


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


def _cash_req(dish, slot, **overrides) -> ReservationRequest:
    defaults = dict(
        trading_day_date=dt.date(2026, 9, 1),
        slot_id=slot.pk,
        payment_method="cash",
        customer_name="Jane Customer",
        customer_mobile_e164="+27821234567",
        lines=[CheckoutLine(dish_id=dish.pk, quantity=1)],
        now=SAME_DAY_BEFORE_CUTOFF,
    )
    defaults.update(overrides)
    return ReservationRequest(**defaults)


class TestCashRequestsView:
    def test_anonymous_redirected_to_login(self, client) -> None:
        resp = client.get(reverse("manage:cash_requests"))
        assert resp.status_code == 302

    def test_lists_only_cash_request_orders(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        cash_order = reserve(_cash_req(dish, slot), biz_settings)
        second_slot = trading_day.slots.create(
            start_at=dt.time(16, 15), end_at=dt.time(16, 30), capacity=5,
        )
        eft_order = reserve(
            _cash_req(dish, second_slot, payment_method="eft", customer_mobile_e164="+27829999999"),
            biz_settings,
        )
        resp = client.get(reverse("manage:cash_requests"))
        assert cash_order.order_number.encode() in resp.content
        assert eft_order.order_number.encode() not in resp.content

    def test_empty_state(self, client) -> None:
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:cash_requests"))
        assert b"No cash requests waiting" in resp.content

    def test_accept_via_the_transition_endpoint(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        order = reserve(_cash_req(dish, slot), biz_settings)

        resp = client.post(
            reverse("manage:api_transition", args=[order.pk]),
            data=json.dumps({"action": "accept_cash", "expected_status": "cash_request"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        order.refresh_from_db()
        assert order.status == OrderStatus.CASH_DUE
        assert order.confirmed_at is not None

    def test_reject_frees_the_cash_cap_for_the_next_request(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        biz_settings.cash_daily_cap = 1
        biz_settings.save(update_fields=["cash_daily_cap"])
        _make_staff()
        _login(client)
        order = reserve(_cash_req(dish, slot), biz_settings)

        # Cap is now full — a second cash request must fail.
        from core.capacity import CapacityError

        with pytest.raises(CapacityError) as exc_info:
            reserve(_cash_req(dish, slot, customer_mobile_e164="+27829999999"), biz_settings)
        assert exc_info.value.code == "cash_cap"

        resp = client.post(
            reverse("manage:api_transition", args=[order.pk]),
            data=json.dumps({
                "action": "reject_cash", "expected_status": "cash_request",
                "reason": "Out of range",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        order.refresh_from_db()
        assert order.status == OrderStatus.CANCELLED
        assert order.payment.status == PaymentStatus.CANCELLED

        # Capacity is freed automatically (live aggregate, not a counter)
        # — the second request now succeeds.
        second = reserve(_cash_req(dish, slot, customer_mobile_e164="+27829999999"), biz_settings)
        assert second.status == OrderStatus.CASH_REQUEST


class TestCashEndToEnd:
    def test_checkout_to_accept_to_kitchen_to_collected_with_cash_amount(
        self, client, biz_settings, dish,
    ) -> None:
        """§20.5's own acceptance line: "Cash: checkout before 10:00 ->
        staff accept -> kitchen -> collected with cash amount."

        Goes through `POST /api/checkout` — the real public endpoint,
        which always uses the real wall clock (no `now` override
        reaches it) — so this builds its own trading day for *real*
        "today" with a late cutoff (23:59), rather than reusing the
        shared `trading_day`/`slot` fixtures' fixed 2026-09-01: cash's
        own `cash_same_day_only` check compares the order's date against
        real `now_sast().date()`, and a fixed future date would fail
        that same-day check regardless of what "today" actually is when
        this test runs.
        """
        from core.models import TradingDay
        from core.tz import now_sast

        today = now_sast().date()
        trading_day = TradingDay.objects.create(
            date=today, is_open=True, window_start=dt.time(16, 0), window_end=dt.time(18, 0),
            cutoff_time=dt.time(23, 59), daily_order_cap=50,
        )
        slot = trading_day.slots.create(
            start_at=dt.time(16, 0), end_at=dt.time(16, 15), capacity=5,
        )

        # 1. Customer checkout via the real public API (milestone 3),
        # not core.capacity.reserve() directly — this is the actual path
        # a cash customer takes.
        checkout_payload = {
            "name": "Jane Customer", "mobile": "0821234567", "note": "",
            "date": trading_day.date.isoformat(), "slot_id": slot.pk,
            "payment_method": "cash",
            "lines": [{"dish_id": dish.pk, "quantity": 2, "option_value_ids": []}],
            "accept_policies": True,
        }
        resp = client.post(
            "/api/checkout", data=json.dumps(checkout_payload), content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="cash-e2e-1",
        )
        assert resp.status_code == 201, resp.content
        order_number = resp.json()["order_number"]

        from core.models import Order

        order = Order.objects.get(order_number=order_number)
        assert order.status == OrderStatus.CASH_REQUEST

        # 2. Staff accepts via the cash requests queue's own endpoint.
        _make_staff()
        _login(client)
        resp = client.post(
            reverse("manage:api_transition", args=[order.pk]),
            data=json.dumps({"action": "accept_cash", "expected_status": "cash_request"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        order.refresh_from_db()
        assert order.status == OrderStatus.CASH_DUE

        # 3. Kitchen: start -> ready (staff.views.kitchen's real board).
        kitchen_resp = client.get(reverse("manage:kitchen"), {"date": trading_day.date.isoformat()})
        assert order_number.encode() in kitchen_resp.content

        actor = Actor(ActorKind.STAFF, User.objects.get(email="manager@example.test"))
        order = apply(order, "start_kitchen", actor, OrderStatus.CASH_DUE)
        order = apply(order, "mark_ready", actor, OrderStatus.IN_KITCHEN)

        collection_resp = client.get(
            reverse("manage:collection"), {"date": trading_day.date.isoformat()},
        )
        assert order_number.encode() in collection_resp.content

        # 4. Collected, with a real cash amount recorded.
        resp = client.post(
            reverse("manage:api_transition", args=[order.pk]),
            data=json.dumps({
                "action": "mark_collected", "expected_status": "ready",
                "payload": {"cash_amount_received_cents": order.total_cents},
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        order.refresh_from_db()
        assert order.status == OrderStatus.COLLECTED
        assert order.payment.status == PaymentStatus.COLLECTED_CASH
        assert order.payment.cash_amount_received_cents == order.total_cents
