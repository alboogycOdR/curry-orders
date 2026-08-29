"""`/healthz` (spec §17.1, RUNBOOK.md "Scheduler heartbeat is stale") —
registered at the root in `config/urls.py`, not namespaced under
`public`/`manage`: it's an ops endpoint (load balancer / uptime check),
not a screen either app's URL space is about.
"""
from __future__ import annotations

from datetime import timedelta

from django.http import HttpRequest, JsonResponse
from django.utils import timezone

from core.models import JobHeartbeat

# RUNBOOK.md: "`/healthz` fails if `job_heartbeats` hasn't updated in > 3
# minutes" — the `heartbeat` job itself ticks every 30s (§17.1), so 3
# minutes is a generous multiple of that, not a tight bound.
STALE_AFTER = timedelta(minutes=3)


def healthz(request: HttpRequest) -> JsonResponse:
    heartbeat = JobHeartbeat.objects.filter(job_name="heartbeat").first()
    if heartbeat is None:
        reason = "no heartbeat recorded yet — is the scheduler process running?"
        return JsonResponse({"status": "fail", "reason": reason}, status=503)

    age = timezone.now() - heartbeat.last_run_at
    if age > STALE_AFTER:
        return JsonResponse(
            {"status": "fail", "reason": f"heartbeat stale ({age.total_seconds():.0f}s old)"},
            status=503,
        )
    if not heartbeat.last_ok:
        return JsonResponse(
            {"status": "fail", "reason": heartbeat.detail or "last heartbeat reported not-ok"},
            status=503,
        )

    return JsonResponse({"status": "ok", "heartbeat_age_seconds": round(age.total_seconds(), 1)})
