"""Integration test for `manage.py create_staff_user` — the missing
piece of RUNBOOK.md's "add a staff user" line (see the command's own
docstring)."""
from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from core.auth import verify_password
from core.models import User, UserRole

pytestmark = pytest.mark.django_db


class TestCreateStaffUser:
    def test_creates_an_owner_with_a_generated_password(self) -> None:
        out = StringIO()
        call_command(
            "create_staff_user", email="owner@example.com", name="Jane", role="owner",
            stdout=out,
        )
        user = User.objects.get(email="owner@example.com")
        assert user.role == UserRole.OWNER
        assert user.must_change_password is True
        assert "Temporary password" in out.getvalue()

    def test_creates_a_manager_with_an_explicit_password(self) -> None:
        call_command(
            "create_staff_user", email="cook@example.com", name="Cook", role="manager",
            password="a specific password", stdout=StringIO(),
        )
        user = User.objects.get(email="cook@example.com")
        assert user.role == UserRole.MANAGER
        assert verify_password("a specific password", user.password_hash)

    def test_refuses_to_overwrite_an_existing_email(self) -> None:
        call_command(
            "create_staff_user", email="dupe@example.com", name="A", role="manager",
            stdout=StringIO(),
        )
        with pytest.raises(CommandError):
            call_command(
                "create_staff_user", email="dupe@example.com", name="B", role="owner",
                stdout=StringIO(),
            )
        # The second (failed) attempt didn't touch the first account.
        assert User.objects.get(email="dupe@example.com").name == "A"

    def test_email_is_matched_case_insensitively(self) -> None:
        call_command(
            "create_staff_user", email="Owner@Example.com", name="A", role="owner",
            stdout=StringIO(),
        )
        with pytest.raises(CommandError):
            call_command(
                "create_staff_user", email="owner@example.com", name="B", role="owner",
                stdout=StringIO(),
            )
