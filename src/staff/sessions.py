"""Staff session management — D-12's "email + password... Session
absolute lifetime 12 hours, sliding idle timeout 2 hours" — built on
Django's own session framework (`django.contrib.sessions`, already
installed) but deliberately **not** `django.contrib.auth`. `core.User` is
a plain Django model, not `AbstractBaseUser`; it stays that way on
purpose — see its own docstring and `docs/DECISIONS.md` D-33. This module
is the whole of "logging a `core.User` in and out": no auth backend, no
`request.user`, no `django.contrib.auth.login()`.

Every check below runs server-side against the session store on every
request (`staff/middleware.py` calls `get_authenticated_staff` once per
request) — the cookie's own expiry (`SESSION_COOKIE_AGE`,
`SESSION_SAVE_EVERY_REQUEST` in `config/settings/base.py`) is a
client-side backstop, never trusted on its own.
"""
from __future__ import annotations

import datetime as dt

from django.http import HttpRequest

from core.models import User

_USER_ID_KEY = "staff_user_id"
_LOGIN_AT_KEY = "staff_login_at"
_LAST_SEEN_AT_KEY = "staff_last_seen_at"

ABSOLUTE_LIFETIME = dt.timedelta(hours=12)
IDLE_TIMEOUT = dt.timedelta(hours=2)


def log_in(request: HttpRequest, user: User, now: dt.datetime) -> None:
    """Starts a new staff session for `user`. Rotates the session key
    first (`cycle_key`) so a session id issued to an anonymous visitor of
    the login page can never be reused post-login — the standard
    session-fixation defence, and cheap insurance since nothing else here
    checks who the pre-login session belonged to.
    """
    request.session.cycle_key()
    request.session[_USER_ID_KEY] = user.pk
    request.session[_LOGIN_AT_KEY] = now.isoformat()
    request.session[_LAST_SEEN_AT_KEY] = now.isoformat()


def log_out(request: HttpRequest) -> None:
    request.session.flush()


def get_authenticated_staff(request: HttpRequest, now: dt.datetime) -> User | None:
    """The logged-in `core.User` for this request, or `None`. Flushes
    any stale/expired session state before returning `None` so a dead
    session id doesn't keep round-tripping forever. Called once per
    request by `StaffSessionMiddleware`, which is what actually sets
    `request.staff_user` — views read that, not this function directly.
    """
    user_id = request.session.get(_USER_ID_KEY)
    if user_id is None:
        return None

    login_at = _parse_session_time(request.session.get(_LOGIN_AT_KEY))
    last_seen_at = _parse_session_time(request.session.get(_LAST_SEEN_AT_KEY))
    if login_at is None or last_seen_at is None:
        request.session.flush()
        return None

    if now - login_at > ABSOLUTE_LIFETIME or now - last_seen_at > IDLE_TIMEOUT:
        request.session.flush()
        return None

    try:
        user = User.objects.get(pk=user_id, active=True)
    except User.DoesNotExist:
        request.session.flush()
        return None

    # Sliding idle timeout: touch last-seen on every authenticated
    # request, not only at login.
    request.session[_LAST_SEEN_AT_KEY] = now.isoformat()
    return user


def _parse_session_time(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None
