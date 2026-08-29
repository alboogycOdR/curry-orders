"""Builds the APScheduler instance for `manage.py run_scheduler` (D-13:
"in-process APScheduler", §17.1's cadence table). One `BlockingScheduler`
per process — this project's "single deployable" (D-13) runs it as its
own `scheduler` container/service (`docker-compose.yml`), separate from
the `web` process, not inside a Django request/response cycle.

Only wires the two jobs milestone 1 needs; see `jobs/tasks.py`'s module
docstring for why the rest of §17.1's table isn't here yet.
"""
from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from . import tasks

logger = logging.getLogger("jobs")

# SAST has no DST (core/tz.py) — a fixed UTC+2 cron trigger is exact,
# unlike most timezones where "daily 00:05" would need real tz-aware
# cron handling to survive a DST transition. POSIX TZ sign convention is
# inverted from what it looks like: "Etc/GMT-2" means UTC+2.
_SAST_CRON_TZ = "Etc/GMT-2"


def _logged(func, job_id: str):
    """Wraps a task so an exception gets one clearly-labelled log line
    (job id) in addition to whatever APScheduler's own executor logs —
    `tasks.py`'s functions already record failure to `JobHeartbeat`
    themselves and re-raise; this doesn't change that, just makes the
    scheduler's own log easier to grep by job name.
    """

    def wrapped():
        try:
            func()
        except Exception:
            logger.exception("scheduled job %r raised", job_id)

    wrapped.__name__ = getattr(func, "__name__", job_id)
    return wrapped


def _now_sast_cron() -> dt.datetime:
    return dt.datetime.now(ZoneInfo(_SAST_CRON_TZ))


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=_SAST_CRON_TZ)

    # §17.1: "daily 00:05 SAST and on startup" — `next_run_time` below is
    # the "on startup" half (fires once immediately when the process
    # starts), not a second trigger.
    scheduler.add_job(
        _logged(tasks.run_materialise_days, "materialise_days"),
        trigger=CronTrigger(hour=0, minute=5, timezone=_SAST_CRON_TZ),
        id="materialise_days",
        name="materialise_days",
        next_run_time=_now_sast_cron(),
        misfire_grace_time=3600,
    )

    # §17.1: "every 30s". No explicit on-startup clause in the spec
    # table, but an immediate first tick means /healthz can go green
    # within seconds of the scheduler starting rather than waiting up to
    # 30s for the first interval to elapse.
    scheduler.add_job(
        _logged(tasks.run_heartbeat, "heartbeat"),
        trigger=IntervalTrigger(seconds=30),
        id="heartbeat",
        name="heartbeat",
        next_run_time=_now_sast_cron(),
        misfire_grace_time=60,
    )

    return scheduler
