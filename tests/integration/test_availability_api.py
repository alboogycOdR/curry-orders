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

    def test_photo_url_is_absolute_not_a_bare_media_path(self, client, biz_settings) -> None:
        """`dish_photo_url()` (core.menu) returns a *relative* `/media/...`
        path whenever neither CDN_BASE_URL nor S3_PUBLIC_ENDPOINT is
        configured — fine for `order.js`, this same view's *web*
        consumer (a browser resolves a root-relative `<img src>` against
        the page's own origin), but silently broken for the Flutter app
        (docs/mobile/FLUTTER_APP_PLAN.md), whose `Image.network()` has no
        "page origin" to resolve against. Found live 2026-09-15: the
        Menu screen showed category chips but zero dish cards — the
        failed image loads never let the widget tree settle. Fixed by
        making this endpoint always return an absolute URL.
        """
        from core.models import Media, MediaKind

        media = Media.objects.create(
            kind=MediaKind.DISH_IMAGE,
            storage_key="dish-images/gatsby.jpg",
            mime_type="image/jpeg",
            byte_size=1000,
            sha256=b"\x00" * 32,
        )
        _make_dish("chicken-curry-roti", "Chicken Curry & Roti", "Roti & Curry", image_media=media)
        target = _tomorrow(biz_settings)

        resp = client.get(
            reverse("public:api_availability"), {"date": target.isoformat()}, SERVER_NAME="example.com",
        )
        (only_dish,) = resp.json()["categories"][0]["dishes"]
        assert only_dish["photo_url"] == "http://example.com/media/dish-images/gatsby.jpg"

    def test_photo_url_is_empty_string_not_a_bogus_absolute_url_when_no_photo(
        self, client, biz_settings,
    ) -> None:
        # A naive `request.build_absolute_uri("")` on an empty photo_url
        # would return the *request's own URL*, not an empty string —
        # the endpoint must special-case this rather than let that
        # happen silently.
        _make_dish("chicken-curry-roti", "Chicken Curry & Roti", "Roti & Curry")
        target = _tomorrow(biz_settings)

        resp = client.get(reverse("public:api_availability"), {"date": target.isoformat()})
        (only_dish,) = resp.json()["categories"][0]["dishes"]
        assert only_dish["photo_url"] == ""

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
        assert body["error"] == "outside_horizon"
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
