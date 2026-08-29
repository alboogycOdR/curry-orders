"""Integration tests for /healthz (spec §17.1, RUNBOOK.md)."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from core.models import JobHeartbeat

pytestmark = pytest.mark.django_db


class TestHealthz:
    def test_fails_with_no_heartbeat_recorded(self, client) -> None:
        resp = client.get(reverse("healthz"))
        assert resp.status_code == 503
        assert resp.json()["status"] == "fail"

    def test_ok_with_a_fresh_heartbeat(self, client) -> None:
        JobHeartbeat.objects.create(job_name="heartbeat", last_run_at=timezone.now(), last_ok=True)
        resp = client.get(reverse("healthz"))
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_fails_when_heartbeat_is_stale(self, client) -> None:
        # RUNBOOK.md: "fails if job_heartbeats hasn't updated in > 3 minutes"
        JobHeartbeat.objects.create(
            job_name="heartbeat",
            last_run_at=timezone.now() - timedelta(minutes=4),
            last_ok=True,
        )
        resp = client.get(reverse("healthz"))
        assert resp.status_code == 503
        assert "stale" in resp.json()["reason"]

    def test_fails_when_last_heartbeat_reported_not_ok(self, client) -> None:
        JobHeartbeat.objects.create(
            job_name="heartbeat", last_run_at=timezone.now(), last_ok=False, detail="db unreachable"
        )
        resp = client.get(reverse("healthz"))
        assert resp.status_code == 503
        assert resp.json()["reason"] == "db unreachable"

    def test_other_job_heartbeats_do_not_substitute_for_the_scheduler_one(self, client) -> None:
        JobHeartbeat.objects.create(
            job_name="materialise_days", last_run_at=timezone.now(), last_ok=True
        )
        resp = client.get(reverse("healthz"))
        assert resp.status_code == 503
