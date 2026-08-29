"""`manage.py run_scheduler` — the scheduler process (D-13, §17.1).
`docker-compose.yml`'s `scheduler` service command; runs forever
(`BlockingScheduler.start()` blocks the calling thread) until killed.
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from jobs.scheduler import build_scheduler

logger = logging.getLogger("jobs")


class Command(BaseCommand):
    help = "Run the background job scheduler (spec §17.1). Blocks until killed."

    def handle(self, *args, **options):
        scheduler = build_scheduler()
        self.stdout.write(self.style.SUCCESS("Scheduler starting — jobs: " + ", ".join(
            job.id for job in scheduler.get_jobs()
        )))
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write("Scheduler stopped.")
