"""Integration tests for jobs/tasks.py's job functions — the scheduler
wiring itself (jobs/scheduler.py) isn't tested here (it's APScheduler
configuration, not application logic); these call the task functions
directly, same as jobs/scheduler.py does on a cadence.
"""
from __future__ import annotations

import pytest

from core.models import JobHeartbeat, TradingDay
from jobs.tasks import run_heartbeat, run_materialise_days

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
