"""Management command to seed the admin staff account and allowlist entry.
Run once on first deploy after migrating:
  python manage.py bootstrap_admin

Reads ADMIN_EMAIL from settings (set via .env). Idempotent — safe to re-run.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import StaffAllowlist, User


class Command(BaseCommand):
    help = "Seed the admin staff account and allowlist entry from settings.ADMIN_EMAIL"

    def handle(self, *args, **kwargs):
        email = getattr(settings, "ADMIN_EMAIL", "").strip()
        if not email:
            self.stderr.write("ADMIN_EMAIL is not set in settings/environment. Aborting.")
            return

        # Upsert StaffAllowlist entry
        entry, created = StaffAllowlist.objects.update_or_create(
            email=email,
            defaults={"role": "admin", "invited_by": None},
        )
        if created:
            self.stdout.write(f"Created allowlist entry for {email} (admin).")
        else:
            self.stdout.write(f"Updated allowlist entry for {email} (admin).")

        # Upsert core.User
        user, created = User.objects.update_or_create(
            email=email,
            defaults={
                "name": email,   # satisfies users_name_length CHECK (≥1 char)
                "role": "admin",
                "active": True,
                "must_change_password": False,
            },
        )
        # Only set password_hash if it's blank (don't overwrite an existing password)
        if not user.password_hash:
            user.password_hash = ""
            user.save(update_fields=["password_hash"])
        if created:
            self.stdout.write(f"Created staff user for {email}.")
        else:
            self.stdout.write(f"Staff user for {email} already exists (updated role/active).")

        self.stdout.write(self.style.SUCCESS(
            f"Done. {email} can now sign in at /manage/login/ using Google or email link."
        ))
