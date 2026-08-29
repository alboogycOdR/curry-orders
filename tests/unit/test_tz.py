"""Unit tests for core/tz.py — spec §8.4 / D-05 / §20.5.

Must cover (§20.5): 09:59:59 vs 10:00:00 SAST boundary, and a
UTC-server-clock case crossing midnight (§18 edge case: "server clock
drift" / "UTC server clock" — 01:30 SAST = previous day 23:30 UTC, since
SAST has no DST and is a fixed UTC+2).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest

from core.tz import SAST, orderable_dates, to_sast

CUTOFF = time(10, 0)
PREORDER_DAYS = 7


def _always_open(_d: date) -> bool:
    return True


def _never_open(_d: date) -> bool:
    return False


class TestToSast:
    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValueError):
            to_sast(datetime(2026, 9, 5, 12, 0))

    def test_utc_to_sast_adds_two_hours(self) -> None:
        utc_dt = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)
        sast_dt = to_sast(utc_dt)
        assert sast_dt.tzinfo is not None
        assert sast_dt.hour == 10
        assert sast_dt.date() == date(2026, 9, 5)

    def test_utc_late_evening_crosses_midnight_into_next_sast_day(self) -> None:
        # 23:30 UTC on 5 Sept = 01:30 SAST on 6 Sept (UTC+2, no DST).
        utc_dt = datetime(2026, 9, 5, 23, 30, tzinfo=timezone.utc)
        sast_dt = to_sast(utc_dt)
        assert sast_dt.date() == date(2026, 9, 6)
        assert sast_dt.time() == time(1, 30)


class TestOrderableDatesCutoffBoundary:
    """09:59:59 vs 10:00:00 SAST — strict inequality (§8.4 point 1)."""

    def test_today_included_at_09_59_59_sast(self) -> None:
        now = datetime(2026, 9, 5, 9, 59, 59, tzinfo=SAST)
        dates = orderable_dates(
            now, is_open=_always_open, cutoff_time=CUTOFF, preorder_days=PREORDER_DAYS
        )
        assert dates[0] == date(2026, 9, 5)
        assert len(dates) == 1 + PREORDER_DAYS

    def test_today_excluded_at_exactly_10_00_00_sast(self) -> None:
        now = datetime(2026, 9, 5, 10, 0, 0, tzinfo=SAST)
        dates = orderable_dates(
            now, is_open=_always_open, cutoff_time=CUTOFF, preorder_days=PREORDER_DAYS
        )
        assert date(2026, 9, 5) not in dates
        assert dates[0] == date(2026, 9, 6)
        assert len(dates) == PREORDER_DAYS

    def test_today_excluded_just_after_cutoff(self) -> None:
        now = datetime(2026, 9, 5, 10, 0, 1, tzinfo=SAST)
        dates = orderable_dates(
            now, is_open=_always_open, cutoff_time=CUTOFF, preorder_days=PREORDER_DAYS
        )
        assert date(2026, 9, 5) not in dates

    def test_today_excluded_when_trading_day_closed_even_before_cutoff(self) -> None:
        now = datetime(2026, 9, 5, 9, 0, 0, tzinfo=SAST)
        dates = orderable_dates(
            now, is_open=_never_open, cutoff_time=CUTOFF, preorder_days=PREORDER_DAYS
        )
        assert date(2026, 9, 5) not in dates
        assert len(dates) == 0  # every day closed in this stub


class TestOrderableDatesUtcServerClock:
    """§20.5 / §18 edge case: server runs in UTC; business rules must
    still evaluate in SAST, including across the UTC midnight boundary."""

    def test_utc_now_just_before_sast_cutoff(self) -> None:
        # 07:59:59 UTC = 09:59:59 SAST -> today still orderable.
        now = datetime(2026, 9, 5, 7, 59, 59, tzinfo=timezone.utc)
        dates = orderable_dates(
            now, is_open=_always_open, cutoff_time=CUTOFF, preorder_days=PREORDER_DAYS
        )
        assert dates[0] == date(2026, 9, 5)

    def test_utc_now_at_sast_cutoff(self) -> None:
        # 08:00:00 UTC = 10:00:00 SAST -> today closed.
        now = datetime(2026, 9, 5, 8, 0, 0, tzinfo=timezone.utc)
        dates = orderable_dates(
            now, is_open=_always_open, cutoff_time=CUTOFF, preorder_days=PREORDER_DAYS
        )
        assert date(2026, 9, 5) not in dates
        assert dates[0] == date(2026, 9, 6)

    def test_utc_late_evening_uses_next_sast_calendar_day(self) -> None:
        # 22:00 UTC on 5 Sept = 00:00 SAST on 6 Sept — a new SAST day has
        # already begun even though the UTC date is still the 5th.
        now = datetime(2026, 9, 5, 22, 0, 0, tzinfo=timezone.utc)
        dates = orderable_dates(
            now, is_open=_always_open, cutoff_time=CUTOFF, preorder_days=PREORDER_DAYS
        )
        assert dates[0] == date(2026, 9, 6)
        assert date(2026, 9, 5) not in dates


class TestOrderableDatesHorizon:
    def test_horizon_is_today_plus_preorder_days_when_all_open(self) -> None:
        now = datetime(2026, 9, 5, 8, 0, 0, tzinfo=SAST)
        dates = orderable_dates(
            now, is_open=_always_open, cutoff_time=CUTOFF, preorder_days=PREORDER_DAYS
        )
        assert dates == [date(2026, 9, 5) + timedelta(days=i) for i in range(8)]
        assert len(dates) == 8

    def test_closed_future_days_are_skipped_not_substituted(self) -> None:
        closed = {date(2026, 9, 7)}

        def is_open(d: date) -> bool:
            return d not in closed

        now = datetime(2026, 9, 5, 8, 0, 0, tzinfo=SAST)
        dates = orderable_dates(now, is_open=is_open, cutoff_time=CUTOFF, preorder_days=PREORDER_DAYS)
        assert date(2026, 9, 7) not in dates
        assert len(dates) == 7  # 8 candidate days minus the one closed day

    def test_zero_preorder_days_is_today_only(self) -> None:
        now = datetime(2026, 9, 5, 8, 0, 0, tzinfo=SAST)
        dates = orderable_dates(now, is_open=_always_open, cutoff_time=CUTOFF, preorder_days=0)
        assert dates == [date(2026, 9, 5)]
