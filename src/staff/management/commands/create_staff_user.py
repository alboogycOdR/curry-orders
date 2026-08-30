"""`manage.py create_staff_user` — the one piece of `RUNBOOK.md`'s
"add a staff user" line that didn't exist yet: everything else (seed_dev)
is dev-only sample data with placeholder emails, never meant to touch a
real deploy.

Usage:
    manage.py create_staff_user --email owner@example.com --name "Jane" --role owner
    manage.py create_staff_user --email cook@example.com --name "Cook" --role manager \
        --password "..."

With no `--password`, generates one and prints it once — never logged,
never stored anywhere but the hash (D-12's Argon2id, `core.auth`).
`must_change_password` defaults to `True` on the model (`core.User`), so
whoever logs in with the printed password is forced to set their own
before doing anything else.
"""
from __future__ import annotations

import secrets

from django.core.management.base import BaseCommand, CommandError

from core.auth import hash_password
from core.models import User, UserRole


class Command(BaseCommand):
    help = "Create a staff (owner/manager) account. See RUNBOOK.md."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument(
            "--role", required=True, choices=[UserRole.OWNER, UserRole.MANAGER],
        )
        parser.add_argument(
            "--password",
            help="Omit to auto-generate one (printed once, not stored in plain text anywhere).",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(
                f"A user with email {email!r} already exists — this command never "
                "overwrites an existing account. Delete it first if that's really "
                "what you want."
            )

        password = options["password"] or secrets.token_urlsafe(18)
        user = User.objects.create(
            email=email,
            name=options["name"],
            role=options["role"],
            password_hash=hash_password(password),
            must_change_password=True,
        )

        self.stdout.write(self.style.SUCCESS(f"Created {user.role} account: {user.email}"))
        if not options["password"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Temporary password (shown once, not stored anywhere in plain "
                    f"text): {password}"
                )
            )
            self.stdout.write("They'll be required to set their own password on first login.")
