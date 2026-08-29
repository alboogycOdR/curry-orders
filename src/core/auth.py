"""Staff password hashing and account-lockout rules (spec §4, D-12).

`core.User` is a plain Django model, not `AbstractBaseUser` — see its own
docstring and `docs/DECISIONS.md` D-33 for why staff auth is a fully
custom session mechanism (`staff/sessions.py`) rather than
`django.contrib.auth`. This module is the framework-agnostic half of
that: password hashing/verification and the failed-login/lockout state
machine, both pure functions of a `core.User` plus a caller-supplied
`now` (never the wall clock directly — keeps this testable without
freezing time globally).

`core/` has no HTTP imports (§17.2); this module doesn't need any —
`.save()` on a `core.User` is the same ORM access `Settings.current()`
already does from `core/models.py`.
"""
from __future__ import annotations

import datetime as dt

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

from .models import User

# D-12: "Five failed logins lock the account for 15 minutes."
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15

_hasher = PasswordHasher()  # argon2id is argon2-cffi's default Type since 2.x


def hash_password(raw_password: str) -> str:
    """Argon2id hash for `User.password_hash` — D-12's "Argon2id hashing"."""
    return _hasher.hash(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    """True iff `raw_password` matches `password_hash`. Never raises on a
    wrong password or a malformed/empty hash (e.g. a user row created
    without one) — both are just "not a match" to a caller checking
    credentials.
    """
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, raw_password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True if the stored hash's parameters are weaker than `_hasher`'s
    current ones (argon2-cffi picks sane defaults; this only matters if
    those defaults are ever tightened later). Callers rehash-on-login,
    the standard way to migrate hash parameters without a bulk reset.
    """
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHash:
        return False


def is_locked_out(user: User, now: dt.datetime) -> bool:
    """`users.locked_until` is set (D-12) once `register_failed_login`
    trips the counter; the lock lifts on its own once `now` passes it —
    no explicit "unlock" action exists or is needed.
    """
    return user.locked_until is not None and now < user.locked_until


def register_failed_login(user: User, now: dt.datetime) -> None:
    """Call once per wrong password. Trips the lock at exactly the 5th
    consecutive failure; further failures while already locked just
    extend nothing (the lock's own expiry is untouched) — the account
    unlocks `LOCKOUT_MINUTES` after the failure that tripped it, not
    after the most recent attempt, so a script hammering a locked
    account can't keep pushing the unlock time out forever.
    """
    user.failed_login_count += 1
    if user.failed_login_count >= MAX_FAILED_LOGINS and not is_locked_out(user, now):
        user.locked_until = now + dt.timedelta(minutes=LOCKOUT_MINUTES)
    user.save(update_fields=["failed_login_count", "locked_until"])


def register_successful_login(user: User, now: dt.datetime) -> None:
    """Clears the failure counter/lock and stamps `last_login_at`."""
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    user.save(update_fields=["failed_login_count", "locked_until", "last_login_at"])
