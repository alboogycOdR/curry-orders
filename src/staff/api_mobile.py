"""Staff-facing JSON API for the Flutter mobile app's staff mode
(docs/mobile/FLUTTER_APP_PLAN.md Phase 6 — "Staff app"). Sibling to
`public.api`'s customer-facing `/api/v1/...` surface, mounted the same
way (session-cookie auth, same CSRF dance) but under `/api/v1/staff/`
and gated by `request.staff_user` instead of the customer session.

Action endpoints already exist and are reused as-is, not duplicated:
`staff.api.transition`/`assign_order`/`lock_prep_list`/`close_out_day`/
`move_all_orders` are already plain session+CSRF-authed JSON endpoints
(built for the web boards' own fetch() calls) — the mobile app calls
them directly, same URLs, same `staff_login_required` gate. This module
only adds what's missing: (1) a JSON-shaped login/logout/me for a
client with no HTML login *page* to redirect to (`staff_login_required`
itself 302s, which is right for the web boards' server-rendered pages
and wrong for a JSON client — see `_staff_login_required_json` below),
and (2) read-shaped JSON for each staff screen's own data, built by
extracting/reusing the same context-building helpers
`staff/views.py`'s server-rendered templates already call, the same
pattern `public/api.py` used for the customer side
(`_order_status_context()` etc.) — never a second copy of the query/
business logic.
"""
from __future__ import annotations

import json
from functools import wraps

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from core.auth import (
    is_locked_out,
    register_failed_login,
    register_successful_login,
    verify_password,
)
from core.models import User

from . import sessions

_ERROR_STATUS = {
    "auth_required": 401,
    "forbidden": 403,
    "validation_error": 400,
    "locked_out": 423,
    "not_found": 404,
}


def _error_response(code: str, message: str, **extra: object) -> JsonResponse:
    status = _ERROR_STATUS.get(code, 422)
    return JsonResponse({"error": code, "message": message, **extra}, status=status)


def staff_login_required_json(view):
    """JSON sibling of `staff.decorators.staff_login_required` — a 401
    body instead of a 302 to `manage:login` (there is no login *page* to
    redirect a JSON client to; the app's own staff-login screen is what
    calls `login_json` below in response to this).
    """
    @wraps(view)
    def wrapped(request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        if request.staff_user is None:
            return _error_response("auth_required", "Sign in to the staff area.")
        return view(request, *args, **kwargs)

    return wrapped


def _user_json(user: User) -> dict[str, object]:
    return {
        "id": user.pk,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "role_display": user.get_role_display(),
        "avatar_url": user.google_avatar_url or "",
        "must_change_password": user.must_change_password,
    }


@require_POST
@csrf_protect
def login_json(request: HttpRequest) -> JsonResponse:
    """`POST /api/v1/staff/auth/login/` — password login only, same
    account/lockout rules as `staff.views.login` (D-12): 5 failed
    attempts locks the account 15 minutes, `must_change_password`
    still has to be handled by the client (it gets `true` back in the
    user object below; the app should route to a change-password screen
    rather than let the session sit there un-rotated the way an
    unattended web redirect loop would).

    Body: `{"email": "...", "password": "..."}`.
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _error_response("validation_error", "Malformed JSON body.")
    if not isinstance(data, dict):
        return _error_response("validation_error", "Malformed JSON body.")

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    now = timezone.now()

    user = User.objects.filter(email=email, active=True).first()
    if user is None:
        # Same generic message as a wrong password (staff.views.login's
        # own reasoning) -- don't let this endpoint confirm which
        # emails have staff accounts.
        return _error_response("validation_error", "Incorrect email or password.")
    if is_locked_out(user, now):
        return _error_response(
            "locked_out",
            "This account is locked for 15 minutes after too many failed attempts.",
        )
    if not verify_password(password, user.password_hash):
        register_failed_login(user, now)
        return _error_response("validation_error", "Incorrect email or password.")

    register_successful_login(user, now)
    sessions.log_in(request, user, now)
    return JsonResponse({"user": _user_json(user)})


@require_POST
@csrf_protect
@staff_login_required_json
def logout_json(request: HttpRequest) -> JsonResponse:
    """`POST /api/v1/staff/auth/logout/`. Flushes the *whole* Django
    session (`staff.sessions.log_out`, unchanged) -- same as the web,
    this also signs out any customer session sharing the same cookie
    (`public.customer_sessions`' `customer_user_id` lives in the same
    session). Not a bug to fix here: it's the existing, already-shipped
    web behaviour (`staff.views.logout`), just reached from a JSON
    client instead of a POST form.
    """
    sessions.log_out(request)
    return JsonResponse({"ok": True})


@require_GET
def me_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/staff/auth/me/` — 200 with the signed-in staff user,
    or a plain `{"user": null}` (200, not 401) when signed out. Deliberately
    *not* gated by `staff_login_required_json`: this is the app's own
    "am I staff, and if so who" probe on launch (mirrors
    `public.api.account_json`'s shape for the customer side, but that one
    401s when signed out because the Account screen treats "signed out" as
    an error state to show a login form for; here, "not staff" is the
    ordinary, expected answer for the ~everyone who isn't -- see
    `mobile/lib/state/staff_auth.dart`).
    """
    if request.staff_user is None:
        return JsonResponse({"user": None})
    return JsonResponse({"user": _user_json(request.staff_user)})
