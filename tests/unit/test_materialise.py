"""Unit test for the pure half of core/materialise.py — `generate_slot_bounds`
(spec §10's slot generation rule). `materialise_day`/`materialise_days`
write to the database (`TradingDay`/`Slot`) and are integration-tested
instead — see tests/integration/test_materialise_db.py.
"""
from __future__ import annotations

from datetime import time

from core.materialise import generate_slot_bounds


class TestGenerateSlotBounds:
    def test_spec_default_window_gives_eight_15_minute_slots(self) -> None:
        # §10's own worked example: 16:00-18:00 / 15 min -> eight slots,
        # 16:00-16:15 through 17:45-18:00.
        bounds = generate_slot_bounds(time(16, 0), time(18, 0), 15)
        assert bounds == [
            (time(16, 0), time(16, 15)),
            (time(16, 15), time(16, 30)),
            (time(16, 30), time(16, 45)),
            (time(16, 45), time(17, 0)),
            (time(17, 0), time(17, 15)),
            (time(17, 15), time(17, 30)),
            (time(17, 30), time(17, 45)),
            (time(17, 45), time(18, 0)),
        ]

    def test_a_partial_final_slot_is_dropped(self) -> None:
        # §10: "emit [t, t+slot_minutes) while t + slot_minutes <=
        # window_end" — a window that doesn't divide evenly by
        # slot_minutes drops the trailing partial slot rather than
        # shrinking it or overrunning window_end.
        bounds = generate_slot_bounds(time(16, 0), time(16, 50), 15)
        assert bounds == [
            (time(16, 0), time(16, 15)),
            (time(16, 15), time(16, 30)),
            (time(16, 30), time(16, 45)),
        ]

    def test_window_shorter_than_one_slot_gives_nothing(self) -> None:
        assert generate_slot_bounds(time(16, 0), time(16, 10), 15) == []

    def test_window_exactly_one_slot(self) -> None:
        assert generate_slot_bounds(time(16, 0), time(16, 15), 15) == [(time(16, 0), time(16, 15))]
