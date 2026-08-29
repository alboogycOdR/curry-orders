"""Unit tests for the pure parts of core/auth.py (spec §4, D-12) — hashing,
verification and the lockout *check* (`is_locked_out`). The two functions
that `.save()` a `User` (`register_failed_login`/`register_successful_login`)
are integration-tested against real Postgres instead — see
tests/integration/test_auth_lockout.py.

None of these touch the database: a `core.User(...)` built in memory
(never `.save()`d) is enough to exercise hashing and the lockout-window
comparison, same as tz/phone/money's existing unit tests.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.auth import hash_password, is_locked_out, needs_rehash, verify_password
from core.models import User, UserRole

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)


def _user(**overrides) -> User:
    defaults = dict(
        email="owner@example.test",
        name="Owner",
        role=UserRole.OWNER,
        password_hash="",
        locked_until=None,
    )
    defaults.update(overrides)
    return User(**defaults)


class TestHashAndVerify:
    def test_hash_then_verify_round_trips(self) -> None:
        hashed = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", hashed)

    def test_wrong_password_fails(self) -> None:
        hashed = hash_password("correct horse battery staple")
        assert not verify_password("wrong password", hashed)

    def test_hash_is_not_the_plaintext(self) -> None:
        hashed = hash_password("correct horse battery staple")
        assert hashed != "correct horse battery staple"
        assert hashed.startswith("$argon2id$")  # argon2-cffi's default Type

    def test_empty_hash_never_matches(self) -> None:
        # A User row created without ever setting password_hash (shouldn't
        # happen via core.auth, but a defensive check on the "not a
        # match" path, not "raises").
        assert not verify_password("anything", "")

    def test_malformed_hash_does_not_raise(self) -> None:
        assert not verify_password("anything", "not-a-real-hash")

    def test_needs_rehash_false_for_a_hash_just_made(self) -> None:
        assert not needs_rehash(hash_password("correct horse battery staple"))

    def test_needs_rehash_false_for_malformed_hash(self) -> None:
        # Never raises — a malformed hash gets caught elsewhere
        # (verify_password returns False for it); this just shouldn't 500.
        assert not needs_rehash("not-a-real-hash")


class TestIsLockedOut:
    def test_no_lock_set(self) -> None:
        assert not is_locked_out(_user(locked_until=None), NOW)

    def test_lock_in_the_future(self) -> None:
        assert is_locked_out(_user(locked_until=NOW + timedelta(minutes=10)), NOW)

    def test_lock_exactly_now_is_not_locked(self) -> None:
        # `now < locked_until`, strict — the boundary instant itself is
        # already unlocked, same "strictly before" convention as
        # core.tz.orderable_dates' cutoff check.
        assert not is_locked_out(_user(locked_until=NOW), NOW)

    def test_lock_in_the_past(self) -> None:
        assert not is_locked_out(_user(locked_until=NOW - timedelta(minutes=1)), NOW)
