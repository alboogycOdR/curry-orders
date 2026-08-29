"""Integration test for `manage.py seed_dev` — the local-dev bootstrap
(spec §21 names it; see the command's own docstring for scope)."""
from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

from core.auth import verify_password
from core.models import Settings, TradingDay, User

pytestmark = pytest.mark.django_db


class TestSeedDev:
    def test_creates_settings_three_staff_and_the_trading_calendar(self) -> None:
        call_command("seed_dev", stdout=StringIO())

        assert Settings.objects.filter(pk=1).exists()
        assert User.objects.count() == 3
        assert User.objects.filter(role="owner").count() == 1
        assert User.objects.filter(role="manager").count() == 2
        assert all(u.must_change_password for u in User.objects.all())
        assert TradingDay.objects.count() == 11

    def test_is_safe_to_run_twice(self) -> None:
        call_command("seed_dev", stdout=StringIO())
        first_hashes = {u.email: u.password_hash for u in User.objects.all()}

        call_command("seed_dev", stdout=StringIO())  # should skip existing users/settings
        assert User.objects.count() == 3
        for user in User.objects.all():
            # not reset to a new temp password on re-run
            assert user.password_hash == first_hashes[user.email]

    def test_printed_temporary_passwords_actually_work(self) -> None:
        out = StringIO()
        call_command("seed_dev", stdout=out)
        output = out.getvalue()

        owner = User.objects.get(role="owner")
        line = next(line for line in output.splitlines() if owner.email in line)
        temp_password = line.rsplit(": ", 1)[-1].strip()
        assert verify_password(temp_password, owner.password_hash)
