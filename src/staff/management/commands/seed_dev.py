"""`manage.py seed_dev` — local-development-only bootstrap.

Spec §21 names two seed commands: `seed_pilot` ("settings with §3
defaults and owner-supplied values from §23; 1 owner + 2 manager users
... monthly dish catalogue from the owner's list; trading days
today+10 open") for the real pilot, and `seed_dev` ("placeholder dishes
and sample orders for local development only"). `seed_pilot` needs real
owner input that spec §23 still lists as Outstanding (bank details, dish
list, ...) — not buildable yet. This is the `seed_dev` half spec already
named, scoped to what milestone 1 needs to be testable end-to-end: a
settings row, staff accounts to log in with, and a materialised trading
calendar. Placeholder dishes/sample orders (the rest of what `seed_dev`
is eventually for) land once `core.Dish`/`core.Order` have real
create-flows to seed against (milestones 2-3).

**Never run this against a production database** — it creates staff
accounts with printed temporary passwords. Nothing here checks
`DEBUG`/environment because the owner-facing `seed_pilot` command is the
intended prod path once it exists; this one stays a plain human judgement
call same as any other `manage.py` command, documented instead of gated.
"""
from __future__ import annotations

import secrets

from django.core.management.base import BaseCommand
from django.db import transaction

from core.auth import hash_password
from core.materialise import materialise_days
from core.models import Settings, User, UserRole
from core.tz import now_sast

_DEV_STAFF = [
    ("owner@example.test", "Dev Owner", UserRole.OWNER),
    ("manager1@example.test", "Dev Manager One", UserRole.MANAGER),
    ("manager2@example.test", "Dev Manager Two", UserRole.MANAGER),
]


class Command(BaseCommand):
    help = "Local dev only: seed a Settings row, three staff accounts, and the trading calendar."

    @transaction.atomic
    def handle(self, *args, **options):
        settings = self._seed_settings()
        self._seed_staff()
        days = materialise_days(now_sast().date(), settings)
        self.stdout.write(self.style.SUCCESS(
            f"Trading calendar: {days[0].date} … {days[-1].date} materialised with slots."
        ))

    def _seed_settings(self) -> Settings:
        settings, created = Settings.objects.get_or_create(
            id=1,
            defaults={"public_site_name": "Brandon's Kitchen (dev)"},
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Settings: created default row."))
        else:
            self.stdout.write("Settings: row already exists, left untouched.")
        return settings

    def _seed_staff(self) -> None:
        for email, name, role in _DEV_STAFF:
            if User.objects.filter(email=email).exists():
                self.stdout.write(f"Staff: {email} already exists, skipped.")
                continue
            temp_password = secrets.token_urlsafe(9)
            User.objects.create(
                email=email,
                name=name,
                role=role,
                password_hash=hash_password(temp_password),
                must_change_password=True,
            )
            self.stdout.write(self.style.SUCCESS(
                f"Staff: created {email} ({role}) — temporary password: {temp_password}"
            ))
