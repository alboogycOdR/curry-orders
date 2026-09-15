"""Staff-facing JSON API for the two owner/admin-only screens — Settings
and Team (docs/mobile/FLUTTER_APP_PLAN.md Phase 6, row 7 of the split).
Sibling to `api_mobile.py` (auth) and `api_mobile_boards.py`/
`api_mobile_collection_cash.py`/`api_mobile_payments.py` (the other
Phase 6 screens) — wired into `/api/v1/staff/` by `urls_api_mobile.py`
(owned elsewhere, not edited here).

Both screens re-derive their data/logic from the existing web views
rather than duplicating it:
- Settings: `staff/views.py::settings_view` (`SettingsForm`'s
  `ModelForm` validation --> `Settings.full_clean()`, same
  `CheckConstraint`s) plus its `_settings_snapshot`/`_diff_settings`
  helpers, imported as-is for the `SettingsEvent` audit diff.
- Team: `staff/views.py::team` and its ad-hoc `_require_admin` decorator
  — the allowlist/live-user/social-identity join and the
  invite/change-role/remove actions are mirrored here field-for-field,
  just JSON-shaped instead of redirect+flash-message shaped.
"""
from __future__ import annotations

import datetime as dt
import json
from functools import wraps

from django.core.exceptions import ValidationError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from core.models import Settings, SettingsEvent, SocialIdentity, StaffAllowlist, UserRole
from core.models import User as CoreUser

from .api_mobile import _error_response, staff_login_required_json
from .views import _diff_settings, _settings_snapshot

_ROLES = (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)


def _owner_or_admin_required(view):
    """Mirrors `staff.decorators.owner_required`'s exact check (this
    project's mobile JSON siblings each re-express the matching web
    decorator's check as a JSON 403 rather than reusing the
    redirect-shaped web decorator directly — see `api_mobile.py`'s own
    `staff_login_required_json` for the same pattern applied to plain
    login).
    """
    @wraps(view)
    def wrapped(request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        if request.staff_user.role not in (UserRole.OWNER, UserRole.ADMIN):
            return _error_response("forbidden", "Owner access only.")
        return view(request, *args, **kwargs)

    return wrapped


def _admin_required(view):
    """Mirrors `staff/views.py::_require_admin`'s exact check."""
    @wraps(view)
    def wrapped(request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        if request.staff_user.role != UserRole.ADMIN:
            return _error_response("forbidden", "Team management requires admin access.")
        return view(request, *args, **kwargs)

    return wrapped


def _json_body(request: HttpRequest) -> dict | None:
    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------- settings


# Field groups mirror `SettingsForm`'s `exclude = ["id", "updated_by",
# "updated_at"]` (every other `Settings` column is owner-editable) —
# grouped here only to pick the right JSON->Python coercion per field,
# not to change which fields are editable.
_SETTINGS_TIME_FIELDS = ("default_window_start", "default_window_end", "same_day_cutoff")
_SETTINGS_INT_FIELDS = (
    "slot_minutes",
    "default_slot_capacity",
    "default_daily_order_cap",
    "preorder_days",
    "eft_hold_minutes",
    "max_hold_extensions",
    "hold_extension_minutes",
    "payment_review_sla_minutes",
    "cash_daily_cap",
    "collection_grace_minutes",
    "proof_retention_days",
    "order_retention_months",
)
_SETTINGS_BOOL_FIELDS = (
    "cash_enabled",
    "cash_same_day_only",
    "assisted_after_cutoff_enabled",
    "vat_registered",
    "sms_enabled",
)
_SETTINGS_TEXT_FIELDS = (
    "public_site_name",
    "collection_address_line",
    "collection_instructions",
    "bank_name",
    "account_name",
    "account_number",
    "branch_code",
    "account_type",
    "support_whatsapp_e164",
    "allergen_disclaimer",
    "home_kitchen_notice",
    "vat_number",
    "sms_ready_template",
)
_SETTINGS_ALL_FIELDS = (
    _SETTINGS_TEXT_FIELDS + _SETTINGS_TIME_FIELDS + _SETTINGS_INT_FIELDS + _SETTINGS_BOOL_FIELDS
)


def _settings_get(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"settings": _settings_snapshot(Settings.current())})


def _settings_post(request: HttpRequest) -> JsonResponse:
    data = _json_body(request)
    if data is None:
        return _error_response("validation_error", "Malformed JSON body.")

    instance = Settings.objects.filter(pk=1).first()
    creating = instance is None
    if creating:
        instance = Settings(id=1)
    before = {} if creating else _settings_snapshot(instance)

    for field in _SETTINGS_ALL_FIELDS:
        if field not in data:
            continue
        raw = data[field]
        try:
            if field in _SETTINGS_TIME_FIELDS:
                value = dt.time.fromisoformat(raw) if isinstance(raw, str) else raw
            elif field in _SETTINGS_INT_FIELDS:
                value = None if raw is None else int(raw)
            elif field in _SETTINGS_BOOL_FIELDS:
                value = bool(raw)
            else:
                value = raw
        except (TypeError, ValueError):
            return _error_response("validation_error", f"Invalid value for {field}.")
        setattr(instance, field, value)

    try:
        instance.full_clean()
    except ValidationError as exc:
        return _error_response("validation_error", str(exc))

    instance.id = 1
    instance.updated_by = request.staff_user
    instance.save()

    diff = _diff_settings(before, _settings_snapshot(instance))
    if diff:
        SettingsEvent.objects.create(user=request.staff_user, diff=diff)

    return JsonResponse({"settings": _settings_snapshot(instance)})


@staff_login_required_json
@_owner_or_admin_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def settings_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/staff/settings/` (current settings) + `POST` (save).
    Owner or Admin only. See `staff/views.py::settings_view` for the web
    equivalent this mirrors.
    """
    if request.method == "GET":
        return _settings_get(request)
    return _settings_post(request)


# ---------------------------------------------------------------- team


def _team_row_json(entry: StaffAllowlist, live_users: dict[str, CoreUser]) -> dict[str, object]:
    return {
        "allowlist_id": entry.pk,
        "email": entry.email,
        "role": entry.role,
        "has_live_account": entry.email.lower() in live_users,
        "signed_in_via_google": SocialIdentity.objects.filter(
            provider="google", email=entry.email
        ).exists(),
        "invited_by_name": entry.invited_by.name if entry.invited_by_id else None,
    }


def _team_get(request: HttpRequest) -> JsonResponse:
    allowlist = StaffAllowlist.objects.select_related("invited_by").order_by("email")
    live_users = {u.email.lower(): u for u in CoreUser.objects.filter(active=True)}
    return JsonResponse({"team": [_team_row_json(e, live_users) for e in allowlist]})


def _team_invite(request: HttpRequest) -> JsonResponse:
    data = _json_body(request)
    if data is None:
        return _error_response("validation_error", "Malformed JSON body.")

    email = str(data.get("email", "")).strip().lower()
    role = data.get("role", "manager")
    if not email:
        return _error_response("validation_error", "Email is required.")
    if role not in _ROLES:
        return _error_response("validation_error", "Invalid role.")

    entry, created = StaffAllowlist.objects.get_or_create(
        email=email, defaults={"role": role, "invited_by": request.staff_user}
    )
    return JsonResponse(
        {
            "allowlist_id": entry.pk,
            "email": entry.email,
            "role": entry.role,
            "already_existed": not created,
        }
    )


@staff_login_required_json
@_admin_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def team_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/staff/team/` (allowlist, joined against live
    `core.User`/Google `SocialIdentity`) + `POST` (invite). Admin only.
    See `staff/views.py::team` for the web equivalent this mirrors.
    """
    if request.method == "GET":
        return _team_get(request)
    return _team_invite(request)


def _team_change_role(request: HttpRequest, entry: StaffAllowlist) -> JsonResponse:
    data = _json_body(request)
    if data is None:
        return _error_response("validation_error", "Malformed JSON body.")

    new_role = data.get("role")
    if new_role not in _ROLES:
        return _error_response("validation_error", "Invalid role.")

    entry.role = new_role
    entry.save(update_fields=["role"])
    # Live-sync (staff/views.py::team's own "change_role" action) — a
    # StaffAllowlist entry can outlive/precede the matching core.User.
    CoreUser.objects.filter(email=entry.email).update(role=new_role)

    live_users = {u.email.lower(): u for u in CoreUser.objects.filter(active=True)}
    return JsonResponse(_team_row_json(entry, live_users))


def _team_remove(request: HttpRequest, entry: StaffAllowlist) -> JsonResponse:
    if entry.email.lower() == request.staff_user.email.lower():
        return _error_response("validation_error", "You cannot remove yourself from the allowlist.")
    entry.delete()
    return JsonResponse({"ok": True})


@staff_login_required_json
@_admin_required
@require_http_methods(["POST", "DELETE"])
@csrf_protect
def team_member_json(request: HttpRequest, allowlist_id: int) -> JsonResponse:
    """`POST` (change role, body `{"role": "..."}`) / `DELETE` (remove)
    for one `StaffAllowlist` row. Admin only. See
    `staff/views.py::team`'s `change_role`/`remove` actions, mirrored
    here.
    """
    entry = StaffAllowlist.objects.filter(pk=allowlist_id).first()
    if entry is None:
        return _error_response("not_found", "Team member not found.")
    if request.method == "DELETE":
        return _team_remove(request, entry)
    return _team_change_role(request, entry)
