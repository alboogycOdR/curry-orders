"""Push notifications (Firebase Cloud Messaging) — mobile
docs/mobile/FLUTTER_APP_PLAN.md Phase 8. Called from a handful of
specific call sites (checkout success, `mark_ready`, `mark_collected`
transitions — see each caller's own comment for why that site and not
inside `core.transitions.apply()` itself) rather than wired into the
transitions engine: sending a push is a best-effort side effect, not
part of any transaction's correctness, and keeping it fully outside
`apply()` means a Firebase outage can never affect an order transition
succeeding or failing.

Every public function here is deliberately fail-soft: `settings.
FIREBASE_CREDENTIALS_PATH` unset (dev/test, or before the one-time
Firebase project setup is finished) makes every send a silent no-op,
and any Firebase API error is caught and logged, never raised — a
notification failing to send must never break the order flow that
triggered it.
"""
from __future__ import annotations

import logging

from django.conf import settings

from core.models import DeviceToken, User

logger = logging.getLogger(__name__)

_app = None
_app_init_attempted = False


def _get_app():
    """Lazily initialises the Firebase Admin app from
    `FIREBASE_CREDENTIALS_PATH`, once per process. Returns `None` if
    unconfigured or initialisation fails — callers treat that exactly
    like "nothing to send to" rather than an error.
    """
    global _app, _app_init_attempted
    if _app_init_attempted:
        return _app
    _app_init_attempted = True

    if not settings.FIREBASE_CREDENTIALS_PATH:
        logger.debug("FIREBASE_CREDENTIALS_PATH not set — push notifications disabled.")
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        _app = firebase_admin.initialize_app(cred)
    except Exception:
        logger.exception("Failed to initialise Firebase Admin — push notifications disabled.")
        _app = None
    return _app


def send_to_user(user: User, *, title: str, body: str, data: dict[str, str] | None = None) -> None:
    """Sends `title`/`body` to every device this staff member has
    registered (`DeviceToken` — a user can have more than one, e.g. a
    shared kitchen tablet plus their own phone). Silently does nothing
    if push isn't configured yet or the user has no registered devices
    — never raises.
    """
    app = _get_app()
    if app is None:
        return

    tokens = list(DeviceToken.objects.filter(staff_user=user).values_list("fcm_token", flat=True))
    if not tokens:
        return

    try:
        from firebase_admin import messaging

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            tokens=tokens,
        )
        response = messaging.send_each_for_multicast(message, app=app)
    except Exception:
        logger.exception("Failed to send push notification to user %s.", user.pk)
        return

    # A token can go stale (app uninstalled, Google Play Services
    # rotated it) — Firebase reports that per-message, not as a whole-
    # request failure. Clean those rows up so this user's next send
    # doesn't keep paying for a dead token, and so DeviceToken doesn't
    # quietly accumulate rows nobody will ever prune otherwise.
    stale_tokens = [
        tokens[i] for i, result in enumerate(response.responses)
        if not result.success and result.exception is not None
        and getattr(result.exception, "code", None) in ("NOT_FOUND", "UNREGISTERED")
    ]
    if stale_tokens:
        DeviceToken.objects.filter(fcm_token__in=stale_tokens).delete()


def notify_staff(users: list[User], *, title: str, body: str, data: dict[str, str] | None = None) -> None:
    """Fan-out helper for events more than one staff member should
    hear about (e.g. "a new order arrived" — every active staff user,
    not just whoever's assigned, since nobody's assigned yet at that
    point). `send_to_user`'s own no-op/fail-soft behaviour applies to
    each recipient independently — one user with no registered device,
    or a send failure for one user, never stops the others.
    """
    for user in users:
        send_to_user(user, title=title, body=body, data=data)
