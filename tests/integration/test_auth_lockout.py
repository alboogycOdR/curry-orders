"""Integration tests for the DB-writing half of core/auth.py — see
tests/unit/test_auth.py for the pure hashing/lockout-check tests.
"""
from __future__ import annotations

import pytest
from django.utils import timezone

from core.auth import (
    MAX_FAILED_LOGINS,
    is_locked_out,
    register_failed_login,
    register_successful_login,
)
from core.models import User, UserRole

pytestmark = pytest.mark.django_db


def _make_user(**overrides) -> User:
    defaults = dict(
        email="owner@example.test", name="Owner", role=UserRole.OWNER, password_hash="x"
    )
    defaults.update(overrides)
    return User.objects.create(**defaults)


class TestRegisterFailedLogin:
    def test_increments_counter(self) -> None:
        user = _make_user()
        register_failed_login(user, timezone.now())
        user.refresh_from_db()
        assert user.failed_login_count == 1
        assert user.locked_until is None

    def test_trips_lock_at_the_fifth_failure(self) -> None:
        user = _make_user()
        now = timezone.now()
        for _ in range(MAX_FAILED_LOGINS - 1):
            register_failed_login(user, now)
        user.refresh_from_db()
        assert user.locked_until is None  # not yet, one short of D-12's five

        register_failed_login(user, now)
        user.refresh_from_db()
        assert user.failed_login_count == MAX_FAILED_LOGINS
        assert is_locked_out(user, now)
        assert user.locked_until == now + timezone.timedelta(minutes=15)

    def test_further_failures_while_locked_do_not_push_the_unlock_time_out(self) -> None:
        user = _make_user()
        now = timezone.now()
        for _ in range(MAX_FAILED_LOGINS):
            register_failed_login(user, now)
        user.refresh_from_db()
        first_lock = user.locked_until

        register_failed_login(user, now + timezone.timedelta(minutes=5))
        user.refresh_from_db()
        assert user.locked_until == first_lock


class TestRegisterSuccessfulLogin:
    def test_clears_lockout_state_and_stamps_last_login(self) -> None:
        soon = timezone.now() + timezone.timedelta(minutes=5)
        user = _make_user(failed_login_count=4, locked_until=soon)
        now = timezone.now()
        register_successful_login(user, now)
        user.refresh_from_db()
        assert user.failed_login_count == 0
        assert user.locked_until is None
        assert user.last_login_at == now
