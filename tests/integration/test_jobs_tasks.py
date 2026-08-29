"""Integration tests for jobs/tasks.py's job functions — the scheduler
wiring itself (jobs/scheduler.py) isn't tested here (it's APScheduler
configuration, not application logic); these call the task functions
directly, same as jobs/scheduler.py does on a cadence.
"""
from __future__ import annotations

import datetime as dt

import pytest

from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.models import JobHeartbeat, OrderStatus, TradingDay
from core.tz import now_sast
from jobs.tasks import run_expire_holds, run_heartbeat, run_materialise_days

pytestmark = pytest.mark.django_db


class TestRunHeartbeat:
    def test_records_an_ok_heartbeat(self) -> None:
        run_heartbeat()
        heartbeat = JobHeartbeat.objects.get(job_name="heartbeat")
        assert heartbeat.last_ok is True

    def test_second_run_updates_the_same_row(self) -> None:
        run_heartbeat()
        first = JobHeartbeat.objects.get(job_name="heartbeat").last_run_at
        run_heartbeat()
        assert JobHeartbeat.objects.filter(job_name="heartbeat").count() == 1
        assert JobHeartbeat.objects.get(job_name="heartbeat").last_run_at >= first


class TestRunMaterialiseDays:
    def test_materialises_the_horizon_and_records_ok(self) -> None:
        run_materialise_days()
        assert TradingDay.objects.count() == 11
        heartbeat = JobHeartbeat.objects.get(job_name="materialise_days")
        assert heartbeat.last_ok is True
        assert "11 trading days" in heartbeat.detail


class TestRunExpireHolds:
    def test_expires_a_lapsed_hold_and_records_the_count(
        self, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = reserve(
            ReservationRequest(
                trading_day_date=dt.date(2026, 9, 1),
                slot_id=slot.pk,
                payment_method="eft",
                customer_name="Jane Customer",
                customer_mobile_e164="+27821234567",
                lines=[CheckoutLine(dish_id=dish.pk, quantity=1)],
                # The day *before* trading_day's 2026-09-01, same
                # convention as test_capacity.py's own NOW — passes
                # horizon/cutoff regardless of what today's real date is.
                now=dt.datetime(2026, 8, 31, 6, 0, tzinfo=dt.UTC),
            ),
            biz_settings,
        )
        # `run_expire_holds()` (unlike core.eft.expire_holds() called
        # directly, see test_eft.py) takes no `now` override — it always
        # reads the real wall clock, so unlike `now` above, this has to
        # be relative to *that*, or it would never actually be in the
        # past when this test runs.
        order.hold_expires_at = now_sast() - dt.timedelta(minutes=1)
        order.save(update_fields=["hold_expires_at"])

        run_expire_holds()

        order.refresh_from_db()
        assert order.status == OrderStatus.PAYMENT_EXPIRED
        heartbeat = JobHeartbeat.objects.get(job_name="expire_holds")
        assert heartbeat.last_ok is True
        assert "1 hold(s) expired" in heartbeat.detail

    def test_a_quiet_run_still_records_ok(self) -> None:
        run_expire_holds()
        heartbeat = JobHeartbeat.objects.get(job_name="expire_holds")
        assert heartbeat.last_ok is True
        assert "0 hold(s) expired" in heartbeat.detail
