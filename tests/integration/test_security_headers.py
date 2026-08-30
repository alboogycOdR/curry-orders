"""Integration tests for the M10 "security headers" checklist item
(spec §16, §20.5, docs/PHASE_2_PLAN.md) — CSP + Permissions-Policy
(`config/security_headers.py`) and `robots.txt` + `X-Robots-Tag`
(`public/views.py::robots_txt`, `staff/middleware.py`).

`X-Content-Type-Options` and `Referrer-Policy` are Django's own
SecurityMiddleware, configured in `settings/prod.py` only (HSTS/SSL
redirect live there too, and don't make sense under the test settings'
plain-HTTP client) — not re-tested here.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from core.auth import hash_password
from core.models import User, UserRole

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple"


def _make_staff(**overrides) -> User:
    defaults = dict(
        email="manager@example.test", name="Manager", role=UserRole.MANAGER,
        password_hash=hash_password(PASSWORD), must_change_password=False,
    )
    defaults.update(overrides)
    return User.objects.create(**defaults)


def _login(client, email: str = "manager@example.test") -> None:
    resp = client.post(reverse("manage:login"), {"email": email, "password": PASSWORD})
    assert resp.status_code == 302


class TestSecurityHeaders:
    def test_csp_present_on_a_public_page(self, client) -> None:
        resp = client.get(reverse("public:home"))
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "object-src 'none'" in csp

    def test_permissions_policy_present(self, client) -> None:
        resp = client.get(reverse("public:home"))
        pp = resp.headers["Permissions-Policy"]
        assert "camera=()" in pp
        assert "geolocation=()" in pp

    def test_headers_present_on_a_staff_page_too(self, client) -> None:
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:inbox"))
        assert "Content-Security-Policy" in resp.headers
        assert "Permissions-Policy" in resp.headers


class TestRobotsTxt:
    def test_robots_txt_disallows_transactional_and_staff_paths(self, client) -> None:
        resp = client.get("/robots.txt")
        assert resp.status_code == 200
        assert resp["Content-Type"] == "text/plain"
        body = resp.content.decode()
        for path in ("/order/", "/checkout/", "/orders/", "/lookup/", "/manage/", "/admin/"):
            assert f"Disallow: {path}" in body

    def test_public_marketing_pages_are_not_disallowed(self, client) -> None:
        body = client.get("/robots.txt").content.decode()
        # Spec §6.1's own sitemap line: /, /menu, /dishes/*, /help,
        # /policies are meant to stay crawlable — none of their prefixes
        # should appear on a Disallow line.
        for path in ("/menu/", "/dishes/", "/help/", "/policies/"):
            assert f"Disallow: {path}" not in body


class TestNavAudienceSplit:
    """The shared base.html header used to list every staff-board link
    (Inbox, Kitchen desk, Payments, ...) to every visitor, logged in or
    not -- not an authorization hole (every manage:* view is already
    @staff_login_required-gated) but a real information-disclosure/UX
    problem: it exposed the whole internal admin URL surface on every
    customer-facing page. request.staff_user now gates a second nav.
    """

    def test_anonymous_visitor_sees_no_staff_nav_links(self, client) -> None:
        resp = client.get(reverse("public:home"))
        content = resp.content.decode()
        assert "Kitchen desk" not in content
        assert "Daily controls" not in content
        assert reverse("manage:kitchen") not in content
        assert reverse("manage:payments") not in content

    def test_anonymous_visitor_still_sees_the_customer_nav(self, client) -> None:
        content = client.get(reverse("public:home")).content.decode()
        assert reverse("public:order") in content
        assert reverse("public:checkout") in content

    def test_logged_in_staff_sees_the_staff_nav(self, client) -> None:
        _make_staff()
        _login(client)
        content = client.get(reverse("manage:inbox")).content.decode()
        assert "Kitchen desk" in content
        assert reverse("manage:payments") in content

    def test_anonymous_visitor_still_has_a_way_to_reach_staff_login(self, client) -> None:
        # Regression: the first cut of this split removed every
        # customer-visible staff link, including the only path a
        # logged-out staff member had to manage:login itself.
        content = client.get(reverse("public:home")).content.decode()
        assert reverse("manage:login") in content

    def test_logged_in_staff_does_not_see_the_login_link_again(self, client) -> None:
        _make_staff()
        _login(client)
        content = client.get(reverse("public:home")).content.decode()
        assert "Staff login" not in content

    def test_staff_dropdown_carries_every_board_including_menu_editor(self, client) -> None:
        # Menu editor previously had no nav link anywhere -- only reachable
        # by typing /manage/menu/ directly.
        _make_staff()
        _login(client)
        content = client.get(reverse("manage:inbox")).content.decode()
        for name in (
            "manage:inbox", "manage:calendar", "manage:kitchen", "manage:collection",
            "manage:payments", "manage:cash_requests", "manage:daily_controls_today",
            "manage:menu_list", "manage:assisted_order_new", "manage:logout",
        ):
            assert reverse(name) in content, f"{name} missing from the staff dropdown"

    def test_settings_link_only_shown_to_owners(self, client) -> None:
        _make_staff(role=UserRole.MANAGER)
        _login(client)
        content = client.get(reverse("manage:inbox")).content.decode()
        assert reverse("manage:settings") not in content

    def test_settings_link_shown_to_owners(self, client) -> None:
        _make_staff(role=UserRole.OWNER)
        _login(client)
        content = client.get(reverse("manage:inbox")).content.decode()
        assert reverse("manage:settings") in content

    def test_every_staff_board_still_sets_the_csrf_cookie_for_its_own_ajax(
        self, client,
    ) -> None:
        # The old per-page account-bar's own {% csrf_token %} was what
        # made Django set the csrftoken cookie each board's JS reads for
        # its fetch() calls (inbox.js, kitchen.js, ...) -- now it's the
        # header dropdown's logout form doing that job instead. Confirm
        # the cookie still lands on a page that isn't the inbox itself.
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:kitchen"))
        assert "csrftoken" in resp.cookies


class TestManageNoindexHeader:
    def test_manage_pages_carry_x_robots_tag_noindex(self, client) -> None:
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:inbox"))
        assert resp["X-Robots-Tag"] == "noindex, nofollow"

    def test_public_pages_do_not_carry_the_manage_header(self, client) -> None:
        resp = client.get(reverse("public:home"))
        assert "X-Robots-Tag" not in resp.headers
