"""Staff-facing views: auth (login/logout/change-password), the
owner-only settings editor, and the kitchen desk — see
`public/views.py`'s module docstring for the "visual pass" framing that
still applies to the kitchen desk's sample run sheet/meters.

Auth is `staff.sessions`, not `django.contrib.auth` — see that module's
docstring and `docs/DECISIONS.md` D-33 for why. The kitchen desk is now
gated by `@staff_login_required`, closing the gap the previous pass
flagged (design handoff README §4: "must be behind auth").
"""
from __future__ import annotations

import datetime as dt
from urllib.parse import urlencode

from django.contrib import messages
from django.forms.models import model_to_dict
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from core.auth import (
    hash_password,
    is_locked_out,
    register_failed_login,
    register_successful_login,
    verify_password,
)
from core.models import Settings, SettingsEvent, User
from core.tz import coerce_time, now_sast

from . import sessions
from .decorators import owner_required, staff_login_required
from .forms import ChangePasswordForm, LoginForm, SettingsForm

_DAY_NAMES_FULL = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
]
_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


# ---------------------------------------------------------------- auth


def _safe_next(request: HttpRequest, candidate: str | None) -> str:
    """Validated `?next=` redirect target, same defence Django's own
    `LoginView` uses (`url_has_allowed_host_and_scheme` — refuses an
    off-site or scheme-relative URL) so a crafted `?next=` can't turn the
    login page into an open redirect. Falls back to the kitchen desk —
    the only built staff screen right now; swap for `/manage/inbox` once
    that's the real default landing (spec §6.2).
    """
    default = reverse("manage:kitchen")
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return default


def login(request: HttpRequest) -> HttpResponse:
    if request.staff_user is not None:
        return redirect(_safe_next(request, request.GET.get("next")))

    error = None
    form = LoginForm(request.POST) if request.method == "POST" else LoginForm()

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        now = timezone.now()

        user = User.objects.filter(email=email, active=True).first()
        if user is None:
            # Same message as a wrong password — D-12 doesn't require
            # this, but there's no reason to let a login form confirm
            # which emails have staff accounts.
            error = "Incorrect email or password."
        elif is_locked_out(user, now):
            error = "This account is locked after too many failed attempts. Try again shortly."
        elif not verify_password(password, user.password_hash):
            register_failed_login(user, now)
            error = "Incorrect email or password."
        else:
            register_successful_login(user, now)
            sessions.log_in(request, user, now)
            next_url = _safe_next(request, request.POST.get("next") or request.GET.get("next"))
            if user.must_change_password:
                query = urlencode({"next": next_url})
                return redirect(f"{reverse('manage:change_password')}?{query}")
            return redirect(next_url)

    return render(request, "staff/login.html", {
        "form": form,
        "error": error,
        "next": request.GET.get("next", ""),
    })


def logout(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    sessions.log_out(request)
    return redirect("manage:login")


@staff_login_required
def change_password(request: HttpRequest) -> HttpResponse:
    # Scope note: `must_change_password` is enforced at the moment of
    # login (above — the post-login redirect goes here, not to `next`)
    # and nowhere else. A user who navigates away from this page before
    # submitting it can still reach other `/manage` pages on that
    # session; D-12's own wording ("forces a change on next login") is
    # about the login transition, not a persistent site-wide gate, and a
    # second enforcement point here would need care to avoid a redirect
    # loop against this same decorator. Revisit if the owner wants it
    # stricter — three staff accounts makes this a low-severity gap for
    # now, not an oversight.
    user = request.staff_user
    next_url = _safe_next(request, request.POST.get("next") or request.GET.get("next"))
    form = ChangePasswordForm(request.POST) if request.method == "POST" else ChangePasswordForm()

    if request.method == "POST" and form.is_valid():
        if not verify_password(form.cleaned_data["current_password"], user.password_hash):
            form.add_error("current_password", "That's not your current password.")
        else:
            user.password_hash = hash_password(form.cleaned_data["new_password"])
            user.must_change_password = False
            user.save(update_fields=["password_hash", "must_change_password"])
            messages.success(request, "Password changed.")
            return redirect(next_url)

    return render(request, "staff/change_password.html", {
        "form": form,
        "next": next_url,
        # Distinguishes "you must do this before continuing" (post owner
        # temp-password reset, D-12) from a voluntary change — same view,
        # different framing in the template.
        "forced": user.must_change_password,
    })


# ---------------------------------------------------------------- settings (owner-only)


def _settings_snapshot(instance: Settings) -> dict:
    """JSON-safe `{field: value}` for `SettingsEvent.diff` (D-24: "Settings
    is a single typed row with an events table") — same exclude set as
    `SettingsForm.Meta.exclude`.
    """
    data = model_to_dict(instance, exclude=["id", "updated_by", "updated_at"])
    return {key: _json_safe(value) for key, value in data.items()}


def _json_safe(value: object) -> object:
    if isinstance(value, (dt.date, dt.time, dt.datetime)):
        return value.isoformat()
    return value


def _diff_settings(before: dict, after: dict) -> dict:
    keys = set(before) | set(after)
    return {
        key: {"old": before.get(key), "new": after.get(key)}
        for key in keys
        if before.get(key) != after.get(key)
    }


@owner_required
def settings_view(request: HttpRequest) -> HttpResponse:
    instance = Settings.objects.filter(pk=1).first()
    creating = instance is None
    if creating:
        instance = Settings(id=1)
    before = {} if creating else _settings_snapshot(instance)

    if request.method == "POST":
        form = SettingsForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.id = 1
            obj.updated_by = request.staff_user
            obj.save()
            diff = _diff_settings(before, _settings_snapshot(obj))
            if diff:
                SettingsEvent.objects.create(user=request.staff_user, diff=diff)
            messages.success(request, "Settings saved.")
            return redirect("manage:settings")
    else:
        form = SettingsForm(instance=instance)

    return render(request, "staff/settings.html", {"form": form, "creating": creating})


# ---------------------------------------------------------------- kitchen desk


# Sample-only run sheet (handoff README §4 "Today's run") — a real version
# is `core.Order`/`core.Payment` rows for the trading day, joined to slots,
# with `advance` as a POST through `core.transitions.apply()` (milestone
# 5/6, spec §12.4/§9). `si` = status index into STATUSES below, matching
# the handoff's own STATUS[]/STATUS_TAG[] arrays and its forward-only
# advance() reducer.
_STATUSES = ["Awaiting payment", "Confirmed", "Cooking", "Ready", "Collected"]
_STATUS_TAG_CLASS = {
    "Awaiting payment": "tag tag-outline",
    "Confirmed": "tag tag-accent",
    "Cooking": "tag tag-accent-2",
    "Ready": "tag tag-accent",
    "Collected": "tag tag-neutral",
}
_SAMPLE_ORDERS = [
    {"ref": "1041", "who": "Naledi M.", "items": "2× Chicken Gatsby", "slot": "16:00",
     "pay": "EFT", "value": "R 190.00", "si": 4},
    {"ref": "1042", "who": "Riaan P.", "items": "1× Full House", "slot": "16:15",
     "pay": "Cash", "value": "R 130.00", "si": 3},
    {"ref": "1043", "who": "Thandi K.", "items": "3× Chicken Roti Roll", "slot": "16:30",
     "pay": "EFT", "value": "R 195.00", "si": 2},
    {"ref": "1044", "who": "Fatima D.", "items": "1× Beef Lasagne, 1× Steak Curry", "slot": "17:00",
     "pay": "EFT", "value": "R 185.00", "si": 1},
    {"ref": "1045", "who": "Josh v/d B.", "items": "2× Steak Masala Gatsby", "slot": "17:30",
     "pay": "Cash", "value": "R 200.00", "si": 0},
    {"ref": "1046", "who": "Ayanda S.", "items": "1× Chicken Curry & Roti", "slot": "17:45",
     "pay": "EFT", "value": "R 85.00", "si": 0},
]


@staff_login_required
def kitchen(request: HttpRequest) -> HttpResponse:
    settings = Settings.current()
    today = now_sast().date()
    today_label = f"{_DAY_NAMES_FULL[today.weekday()]} {today.day} {_MONTH_NAMES[today.month - 1]}"
    service_window = (
        f"{coerce_time(settings.default_window_start).strftime('%H:%M')}"
        f"–{coerce_time(settings.default_window_end).strftime('%H:%M')}"
    )
    orders = [
        {**o, "status": _STATUSES[o["si"]], "tag_class": _STATUS_TAG_CLASS[_STATUSES[o["si"]]]}
        for o in _SAMPLE_ORDERS
    ]
    return render(request, "staff/kitchen.html", {
        "today_label": today_label,
        "service_window": service_window,
        "orders": orders,
        "statuses": _STATUSES,
        "status_tag_class": _STATUS_TAG_CLASS,
        # Sample-only capacity meters (handoff README §4) — real figures
        # are `core.Order`/`core.Payment` aggregates for the trading day
        # against `Settings`/`TradingDay` ceilings (milestone 6, §8.2).
        "meter_orders": {"value": 18, "of": 24, "label": "of 24 orders secured"},
        "meter_cash": {"value": "R 420", "of": "R 600", "label": "of R 600 cash ceiling"},
        "meter_dish": {"value": 12, "of": 20, "label": "of 20 Gatsby loaves left"},
    })
