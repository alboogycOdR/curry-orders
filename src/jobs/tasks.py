"""Job functions (spec §17.1) — the scheduler-agnostic half. Each
function does one job's unit of work and reports it to `core.JobHeartbeat`
via `_record`; `jobs/scheduler.py` owns *when* these run (cadence,
startup behaviour), never the logic itself, so a test or a one-off
`manage.py` invocation can call a task directly without spinning up
APScheduler.

Only the two jobs milestone 1 needs are implemented here —
`materialise_days` and `heartbeat`. The rest of §17.1's table
(`expire_holds`, `close_out_days`, `purge_proofs`,
`purge_throttle_and_idempotency`, `disk_check`) depends on domain
machinery (`core.capacity`/`core.transitions`, real `Order`/`Media` rows)
that doesn't exist yet — later milestones add functions here, not a
parallel module.
"""
from __future__ import annotations

import logging

from django.utils import timezone

from core.materialise import materialise_days as _materialise_days
from core.models import JobHeartbeat, Settings
from core.tz import now_sast

logger = logging.getLogger("jobs")


def _record(job_name: str, ok: bool, detail: str = "") -> None:
    JobHeartbeat.objects.update_or_create(
        job_name=job_name,
        defaults={"last_run_at": timezone.now(), "last_ok": ok, "detail": detail},
    )


def run_materialise_days() -> None:
    """§17.1: "daily 00:05 SAST and on startup". Ensures `today …
    today+10` exist with slots (`core.materialise.materialise_days`) —
    see that module for why this is safe to call repeatedly.
    """
    try:
        today = now_sast().date()
        days = _materialise_days(today, Settings.current())
        detail = f"{len(days)} trading days through {days[-1].date}"
        _record("materialise_days", ok=True, detail=detail)
    except Exception:
        logger.exception("materialise_days job failed")
        _record("materialise_days", ok=False, detail="see server logs")
        raise


def run_heartbeat() -> None:
    """§17.1: "every 30s; /healthz fails if stale > 3 min". Deliberately
    the simplest possible job — its only purpose is proving the scheduler
    process itself is alive; anything more elaborate here would just add
    another way for the liveness signal to be wrong.
    """
    _record("heartbeat", ok=True)
