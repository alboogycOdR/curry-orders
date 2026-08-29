"""Trading-day + slot materialisation (spec §10, §17.1's `materialise_days`
job, milestone 1's other half besides staff auth).

`core/` has no HTTP imports (§17.2); the DB access here (`get_or_create`,
`bulk_create`) is the same class of ORM use `Settings.current()` already
has in `core/models.py` — this module owns the *rule*, callers (the
`jobs` app's scheduler, and any one-off management command) own *when*
it runs.
"""
from __future__ import annotations

import datetime as dt

from .models import Settings, Slot, TradingDay
from .tz import coerce_time

# §17.1: "Ensure today … today+10 exist with slots" — 11 calendar dates.
MATERIALISE_HORIZON_DAYS = 11


def generate_slot_bounds(
    window_start: dt.time, window_end: dt.time, slot_minutes: int
) -> list[tuple[dt.time, dt.time]]:
    """§10's generation rule verbatim: starting at `window_start`, emit
    `[t, t+slot_minutes)` while `t + slot_minutes <= window_end`.
    """
    bounds = []
    cur = window_start.hour * 60 + window_start.minute
    end = window_end.hour * 60 + window_end.minute
    while cur + slot_minutes <= end:
        start = dt.time(cur // 60, cur % 60)
        cur += slot_minutes
        bounds.append((start, dt.time(cur // 60, cur % 60)))
    return bounds


def generate_slots(trading_day: TradingDay, default_capacity: int, slot_minutes: int) -> None:
    """Insert any of `trading_day`'s own window's slots that don't exist
    yet (by `start_at`) — idempotent, so re-running after staff have
    edited or closed some slots never touches the ones already there.
    §10: full window-change handling ("changing the window regenerates
    only empty future slots") is daily-controls work (milestone 8, spec
    §12.8) — this is just the initial fill.
    """
    existing_starts = set(trading_day.slots.values_list("start_at", flat=True))
    bounds = generate_slot_bounds(trading_day.window_start, trading_day.window_end, slot_minutes)
    new_slots = [
        Slot(trading_day=trading_day, start_at=start, end_at=end, capacity=default_capacity)
        for start, end in bounds
        if start not in existing_starts
    ]
    if new_slots:
        Slot.objects.bulk_create(new_slots)


def materialise_day(date: dt.date, settings: Settings) -> TradingDay:
    """Ensure a `TradingDay` row exists for `date`. `get_or_create` —
    seeded from `settings`' current defaults only the first time; a day
    staff have already customised (window, cap, closed slots, ...) is
    never overwritten by a later run over the same date.
    """
    trading_day, created = TradingDay.objects.get_or_create(
        date=date,
        defaults={
            "is_open": True,
            "window_start": coerce_time(settings.default_window_start),
            "window_end": coerce_time(settings.default_window_end),
            "cutoff_time": coerce_time(settings.same_day_cutoff),
            "daily_order_cap": settings.default_daily_order_cap,
        },
    )
    if created:
        generate_slots(trading_day, settings.default_slot_capacity, settings.slot_minutes)
    return trading_day


def materialise_days(
    today: dt.date, settings: Settings, count: int = MATERIALISE_HORIZON_DAYS
) -> list[TradingDay]:
    """`today … today+(count-1)` — the §17.1 job itself, called with
    `count` defaulting to the spec's 11-date horizon. `today` is always
    the caller's job (SAST calendar date via `core.tz.now_sast().date()`
    — this module doesn't read a clock itself, same reasoning as
    `core.auth`'s explicit `now` parameter).
    """
    return [materialise_day(today + dt.timedelta(days=i), settings) for i in range(count)]
