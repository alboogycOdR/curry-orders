"""Integration tests for `GET /api/availability?date=` (Monday-sprint
Phase 1a, docs/MONDAY_SPRINT.md) — the fix for the order screen's real
stale-slot bug: switching the collection date previously left the
first orderable day's dishes/slots on screen (and a now-invalid slot ID
in client state) no matter which day was actually picked.
"""
from __future__ import annotations

import datetime as dt

import pytest
from django.urls import reverse

from core.materialise import materialise_days
from core.models import DayDishAvailability, Dish
from core.tz import now_sast

pytestmark = pytest.mark.django_db


def _make_dish(slug: str, name: str, category: str, price_cents: int = 8500, **overrides) -> Dish:
    defaults = dict(
        slug=slug, name=name, category=category, price_cents=price_cents,
        is_active_on_menu=True,
    )
    defaults.update(overrides)
    return Dish.objects.create(**defaults)


def _tomorrow(biz_settings) -> dt.date:
    """A real date inside the orderable horizon, computed off the actual
    wall clock (not a fixed calendar date — this endpoint's own horizon
    check depends on when the test runs)."""
    today = now_sast().date()
    materialise_days(today, biz_settings, count=biz_settings.preorder_days + 1)
    return today + dt.timedelta(days=1)


class TestAvailabilityApi:
    def test_returns_dishes_and_slots_for_the_requested_date(self, client, biz_settings) -> None:
        _make_dish("chicken-curry-roti", "Chicken Curry & Roti", "Roti & Curry", 8500)
        _make_dish("beef-lasagne", "Beef Lasagne", "Italian Lasagne", 9000)
        target = _tomorrow(biz_settings)

        resp = client.get(reverse("public:api_availability"), {"date": target.isoformat()})
        assert resp.status_code == 200
        body = resp.json()
        assert body["date"] == target.isoformat()

        names = {
            dish["name"]
            for category in body["categories"]
            for dish in category["dishes"]
        }
        assert names == {"Chicken Curry & Roti", "Beef Lasagne"}
        # A trading day materialised from Settings' own defaults gets
        # real slots too — not an empty list.
        assert len(body["slots"]) > 0
        assert set(body["slots"][0].keys()) == {"id", "label", "full"}

    def test_dish_unavailable_on_this_specific_date_is_flagged_sold_out(
        self, client, biz_settings,
    ) -> None:
        dish = _make_dish("chicken-curry-roti", "Chicken Curry & Roti", "Roti & Curry")
        target = _tomorrow(biz_settings)
        from core.models import TradingDay

        trading_day = TradingDay.objects.get(date=target)
        DayDishAvailability.objects.create(
            trading_day=trading_day, dish=dish, is_available=False,
        )

        resp = client.get(reverse("public:api_availability"), {"date": target.isoformat()})
        body = resp.json()
        (only_dish,) = body["categories"][0]["dishes"]
        assert only_dish["sold_out"] is True

    def test_missing_date_is_a_validation_error(self, client, biz_settings) -> None:
        resp = client.get(reverse("public:api_availability"))
        assert resp.status_code == 400
        assert resp.json()["error"] == "validation_error"

    def test_malformed_date_is_a_validation_error(self, client, biz_settings) -> None:
        resp = client.get(reverse("public:api_availability"), {"date": "not-a-date"})
        assert resp.status_code == 400
        assert resp.json()["error"] == "validation_error"

    def test_date_outside_the_orderable_horizon_is_rejected_not_silently_clamped(
        self, client, biz_settings,
    ) -> None:
        # Far enough out to be outside any reasonable preorder_days
        # setting, regardless of what "today" is when this runs.
        far_future = (now_sast().date() + dt.timedelta(days=60)).isoformat()
        resp = client.get(reverse("public:api_availability"), {"date": far_future})
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"
        # It must actually refuse, not quietly substitute a different
        # date and return 200 for it -- that would just relocate the
        # stale-data bug this endpoint exists to fix.
        assert "date" not in body or body.get("date") != far_future

    def test_past_date_is_rejected(self, client, biz_settings) -> None:
        yesterday = (now_sast().date() - dt.timedelta(days=1)).isoformat()
        resp = client.get(reverse("public:api_availability"), {"date": yesterday})
        assert resp.status_code == 400

    def test_get_only(self, client, biz_settings) -> None:
        resp = client.post(reverse("public:api_availability"), {"date": "2026-09-01"})
        assert resp.status_code == 405
