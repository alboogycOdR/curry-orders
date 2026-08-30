"""`StaffSessionMiddleware` — resolves `request.staff_user` (a
`core.User` or `None`) once per request, so views and templates never
call `staff.sessions.get_authenticated_staff` themselves. See
`staff/sessions.py`'s module docstring for why this exists instead of
`django.contrib.auth`'s `AuthenticationMiddleware`/`request.user` (which
still runs too, for `django.contrib.admin` — the two are independent and
don't conflict).

Registered in `config/settings/base.py`'s `MIDDLEWARE`, after
`SessionMiddleware` (needs `request.session`) — order relative to
`AuthenticationMiddleware` doesn't matter since they touch unrelated
state.
"""
from __future__ import annotations

from django.utils import timezone

from . import sessions


class StaffSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.staff_user = sessions.get_authenticated_staff(request, timezone.now())
        response = self.get_response(request)
        if request.path.startswith("/manage/"):
            # §21 go-live item 7 ("robots.txt and noindex verified with a
            # crawler check") — everything staff-only, header-level rather
            # than per-template meta tags, so a new /manage/ page can't
            # forget it. robots.txt (public/views.py::robots_txt) already
            # disallows the whole prefix; this is the belt to that braces
            # for a crawler that ignores robots.txt outright.
            response.setdefault("X-Robots-Tag", "noindex, nofollow")
        return response
