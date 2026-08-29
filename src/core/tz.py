"""SAST (Africa/Johannesburg, UTC+2, no DST) conversion helpers and the
orderable-dates rule (spec §8.4, D-05).

`core/` has no HTTP imports (§17.2) and everything here is a pure function
of its arguments plus, for `now_sast()`, Django's own tz-aware clock — no
capacity/DB logic. That belongs to `core/capacity.py` in a later milestone
(spec §8); this module only answers "what SAST date/time is it" and "which
dates are orderable given that", independent of any particular trading
day's row.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone as dj_timezone

SAST = ZoneInfo("Africa/Johannesburg")


def to_sast(dt: datetime) -> datetime:
    """Convert an aware datetime (typically UTC, as stored — §16) to SAST.

    Raises ValueError on a naive datetime: every timestamp in this system
    is timestamptz/USE_TZ=True, so a naive value here is a bug upstream,
    not a case to silently guess about.
    """
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError("to_sast() requires an aware datetime")
    return dt.astimezone(SAST)


def now_sast() -> datetime:
    """Current time in SAST, derived from Django's tz-aware `now()`
    (which is UTC per USE_TZ=True) — never from the host clock directly.
    Safe to call on a server whose OS clock is UTC (Clawsrv, §17.5)."""
    return to_sast(dj_timezone.now())


def coerce_time(value: time | str) -> time:
    """`Settings.default_window_start`/`default_window_end`/
    `same_day_cutoff` (core/models.py, §7.2) declare "HH:MM"-string
    defaults — Django only parses those to a real `datetime.time` on
    save/refresh-from-db, so an unsaved `Settings()` fallback instance
    (e.g. `Settings.current()` pre-seed) hands one of these back as the
    raw string instead. Every caller that reads a `Settings` time field
    without knowing whether the row was ever saved goes through this
    rather than crashing on `.hour`/`.strftime()`.
    """
    if isinstance(value, str):
        return datetime.strptime(value, "%H:%M").time()
    return value


def orderable_dates(
    now: datetime,
    *,
    is_open: Callable[[date], bool],
    cutoff_time: time,
    preorder_days: int,
) -> list[date]:
    """`orderable_dates(now_sast)` per spec §8.4 / D-05.

    1. `today` (the SAST calendar date of `now`) is included only if
       `is_open(today)` and `now`'s SAST time-of-day is strictly before
       `cutoff_time` (at exactly the cutoff, today is closed).
    2. Then each of `today+1 .. today+preorder_days` for which
       `is_open(date)` is true.

    `now` may be any aware datetime, including a UTC server clock — it is
    converted to SAST internally, so a caller passing 23:30 UTC (which is
    01:30 SAST the *next* calendar day, SAST has no DST) gets the correct
    SAST calendar date without doing that math itself (spec §20.5, §18
    edge case: UTC-server-clock crossing midnight).

    `is_open` is an injected lookup (e.g. `trading_days.is_open` for a
    given date) rather than a query run in here, keeping this function
    pure and unit-testable without a database — the real lookup and any
    lazy materialisation of missing trading_days rows (§7.5) belongs to
    the capacity/ordering layer, not this module.
    """
    sast_now = to_sast(now)
    today = sast_now.date()

    dates: list[date] = []
    if is_open(today) and sast_now.time() < cutoff_time:
        dates.append(today)

    for offset in range(1, preorder_days + 1):
        d = today + timedelta(days=offset)
        if is_open(d):
            dates.append(d)

    return dates
