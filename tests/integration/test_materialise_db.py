"""Integration tests for the DB-writing half of core/materialise.py — see
tests/unit/test_materialise.py for the pure `generate_slot_bounds` tests.
"""
from __future__ import annotations

from datetime import date, time

import pytest

from core.materialise import MATERIALISE_HORIZON_DAYS, materialise_day, materialise_days
from core.models import Settings, Slot, TradingDay

pytestmark = pytest.mark.django_db


class TestMaterialiseDay:
    def test_creates_trading_day_seeded_from_settings(self) -> None:
        settings = Settings.current()
        d = date(2026, 9, 1)
        trading_day = materialise_day(d, settings)

        assert trading_day.date == d
        assert trading_day.is_open is True
        assert trading_day.window_start == time(16, 0)
        assert trading_day.window_end == time(18, 0)
        assert trading_day.cutoff_time == time(10, 0)
        assert trading_day.daily_order_cap == settings.default_daily_order_cap

    def test_creates_the_spec_default_eight_slots(self) -> None:
        settings = Settings.current()
        trading_day = materialise_day(date(2026, 9, 1), settings)
        slots = list(trading_day.slots.order_by("start_at"))
        assert len(slots) == 8
        assert slots[0].start_at == time(16, 0)
        assert slots[0].end_at == time(16, 15)
        assert slots[0].capacity == settings.default_slot_capacity
        assert slots[-1].end_at == time(18, 0)

    def test_is_idempotent(self) -> None:
        settings = Settings.current()
        d = date(2026, 9, 1)
        materialise_day(d, settings)
        materialise_day(d, settings)  # second call, same date
        assert TradingDay.objects.filter(date=d).count() == 1
        assert Slot.objects.filter(trading_day=d).count() == 8

    def test_never_overwrites_a_day_staff_have_already_customised(self) -> None:
        settings = Settings.current()
        d = date(2026, 9, 1)
        trading_day = materialise_day(d, settings)

        # Staff close the day and shrink a slot's capacity (§10: "Staff
        # may close a slot, change its capacity... or change the day's
        # window").
        trading_day.is_open = False
        trading_day.save(update_fields=["is_open"])
        first_slot = trading_day.slots.order_by("start_at").first()
        first_slot.capacity = 3
        first_slot.save(update_fields=["capacity"])

        materialise_day(d, settings)  # re-run, e.g. next day's scheduler tick

        trading_day.refresh_from_db()
        first_slot.refresh_from_db()
        assert trading_day.is_open is False
        assert first_slot.capacity == 3


class TestMaterialiseDays:
    def test_default_horizon_is_eleven_dates(self) -> None:
        settings = Settings.current()
        today = date(2026, 9, 1)
        days = materialise_days(today, settings)
        assert len(days) == MATERIALISE_HORIZON_DAYS == 11
        assert [d.date for d in days] == [date(2026, 9, 1 + i) for i in range(11)]

    def test_custom_count(self) -> None:
        settings = Settings.current()
        days = materialise_days(date(2026, 9, 1), settings, count=3)
        assert len(days) == 3
