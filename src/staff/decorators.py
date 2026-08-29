"""View decorators built on `request.staff_user` (`staff/middleware.py`)."""
from __future__ import annotations

from functools import wraps
from urllib.parse import urlencode

from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse

from core.models import UserRole


def staff_login_required(view):
    """Redirects an anonymous request to `manage:login` with `?next=`
    set to the original path, same convention as
    `django.contrib.auth.decorators.login_required` (harness-familiar
    even though this isn't that machinery — see `staff/sessions.py`).
    """
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.staff_user is None:
            login_url = reverse("manage:login")
            return redirect(f"{login_url}?{urlencode({'next': request.get_full_path()})}")
        return view(request, *args, **kwargs)

    return wrapped


def owner_required(view):
    """`staff_login_required` plus spec §4's owner-only gate ("Owner:
    everything [managers get] plus settings, staff admin, owner-only
    exceptions"). 403s a logged-in manager rather than redirecting them
    somewhere that doesn't exist for their role.
    """
    @staff_login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.staff_user.role != UserRole.OWNER:
            return HttpResponseForbidden("Owner access only.")
        return view(request, *args, **kwargs)

    return wrapped
