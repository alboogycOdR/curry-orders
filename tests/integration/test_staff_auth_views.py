"""Integration tests for the staff auth flow and the owner-only settings
editor (spec §4/D-12, §6.2) — staff/views.py + staff/sessions.py +
staff/middleware.py + staff/decorators.py end to end through the real
Django test client (session cookies included), against real Postgres.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from core.auth import hash_password, verify_password
from core.models import Settings, SettingsEvent, User, UserRole

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple"


def _make_user(**overrides) -> User:
    defaults = dict(
        email="owner@example.test",
        name="Owner",
        role=UserRole.OWNER,
        password_hash=hash_password(PASSWORD),
        must_change_password=False,
    )
    defaults.update(overrides)
    return User.objects.create(**defaults)


def _post_login(client, password: str = PASSWORD, email: str = "owner@example.test"):
    return client.post(reverse("manage:login"), {"email": email, "password": password})


class TestKitchenGating:
    def test_anonymous_redirected_to_login(self, client) -> None:
        resp = client.get(reverse("manage:kitchen"))
        assert resp.status_code == 302
        assert resp.url.startswith(reverse("manage:login"))
        assert "next=%2Fmanage%2Fkitchen%2F" in resp.url

    def test_logged_in_staff_can_view_it(self, client) -> None:
        _make_user()
        _post_login(client)
        resp = client.get(reverse("manage:kitchen"))
        assert resp.status_code == 200


class TestLogin:
    def test_wrong_password_shows_generic_error(self, client) -> None:
        _make_user()
        resp = _post_login(client, password="wrong")
        assert resp.status_code == 200
        assert b"Incorrect email or password" in resp.content

    def test_unknown_email_shows_the_same_generic_error(self, client) -> None:
        resp = _post_login(client, email="nobody@example.test", password="x")
        assert b"Incorrect email or password" in resp.content

    def test_five_failures_lock_the_account(self, client) -> None:
        _make_user()
        for _ in range(5):
            _post_login(client, password="wrong")
        resp = _post_login(client)
        assert b"locked" in resp.content

    def test_correct_password_logs_in_and_redirects_to_inbox_by_default(self, client) -> None:
        _make_user()
        resp = _post_login(client)
        assert resp.status_code == 302
        assert resp.url == reverse("manage:inbox")

    def test_next_param_is_honoured(self, client) -> None:
        _make_user()
        settings_url = reverse("manage:settings")
        resp = client.post(
            f"{reverse('manage:login')}?next={settings_url}",
            {"email": "owner@example.test", "password": PASSWORD, "next": settings_url},
        )
        assert resp.url == settings_url

    def test_off_site_next_is_ignored(self, client) -> None:
        _make_user()
        resp = client.post(
            reverse("manage:login"),
            {"email": "owner@example.test", "password": PASSWORD, "next": "https://evil.example/"},
        )
        assert resp.url == reverse("manage:inbox")

    def test_must_change_password_redirects_there_instead_of_next(self, client) -> None:
        _make_user(must_change_password=True)
        resp = _post_login(client)
        assert resp.url.startswith(reverse("manage:change_password"))

    def test_inactive_account_cannot_log_in(self, client) -> None:
        _make_user(active=False)
        resp = _post_login(client)
        assert b"Incorrect email or password" in resp.content

    def test_already_logged_in_get_redirects_away_from_login_form(self, client) -> None:
        _make_user()
        _post_login(client)
        resp = client.get(reverse("manage:login"))
        assert resp.status_code == 302


class TestLogout:
    def test_logout_requires_post(self, client) -> None:
        resp = client.get(reverse("manage:logout"))
        assert resp.status_code == 405

    def test_logout_ends_the_session(self, client) -> None:
        _make_user()
        _post_login(client)
        assert client.get(reverse("manage:kitchen")).status_code == 200

        client.post(reverse("manage:logout"))
        resp = client.get(reverse("manage:kitchen"))
        assert resp.status_code == 302


class TestChangePassword:
    def test_requires_login(self, client) -> None:
        resp = client.get(reverse("manage:change_password"))
        assert resp.status_code == 302

    def test_wrong_current_password_rejected(self, client) -> None:
        _make_user()
        _post_login(client)
        resp = client.post(reverse("manage:change_password"), {
            "current_password": "not-it",
            "new_password": "brand-new-password-123",
            "confirm_password": "brand-new-password-123",
        })
        assert resp.status_code == 200
        assert b"not your current password" in resp.content

    def test_mismatched_confirmation_rejected(self, client) -> None:
        _make_user()
        _post_login(client)
        resp = client.post(reverse("manage:change_password"), {
            "current_password": PASSWORD,
            "new_password": "brand-new-password-123",
            "confirm_password": "something-else-entirely",
        })
        assert b"Doesn" in resp.content  # "Doesn't match the new password."

    def test_successful_change_clears_must_change_password_and_updates_hash(self, client) -> None:
        user = _make_user(must_change_password=True)
        _post_login(client)
        resp = client.post(reverse("manage:change_password"), {
            "current_password": PASSWORD,
            "new_password": "brand-new-password-123",
            "confirm_password": "brand-new-password-123",
        })
        assert resp.status_code == 302
        user.refresh_from_db()
        assert user.must_change_password is False
        assert verify_password("brand-new-password-123", user.password_hash)
        assert not verify_password(PASSWORD, user.password_hash)


class TestSettingsView:
    def _valid_payload(self) -> dict:
        return {
            "public_site_name": "Brandon's Kitchen",
            "default_window_start": "16:00",
            "default_window_end": "18:00",
            "slot_minutes": "15",
            "default_slot_capacity": "13",
            "default_daily_order_cap": "100",
            "same_day_cutoff": "10:00",
            "preorder_days": "7",
            "eft_hold_minutes": "30",
            "max_hold_extensions": "1",
            "hold_extension_minutes": "15",
            "payment_review_sla_minutes": "15",
            "cash_daily_cap": "20",
            "collection_grace_minutes": "15",
            "proof_retention_days": "90",
            "order_retention_months": "18",
            "sms_ready_template": "{site}: order {order_number} is ready.",
        }

    def test_manager_gets_403(self, client) -> None:
        _make_user(email="mgr@example.test", role=UserRole.MANAGER)
        _post_login(client, email="mgr@example.test")
        resp = client.get(reverse("manage:settings"))
        assert resp.status_code == 403

    def test_owner_can_view_and_save(self, client) -> None:
        _make_user()
        _post_login(client)
        assert client.get(reverse("manage:settings")).status_code == 200

        resp = client.post(reverse("manage:settings"), self._valid_payload())
        assert resp.status_code == 302
        assert Settings.objects.get(pk=1).public_site_name == "Brandon's Kitchen"

    def test_save_writes_a_settings_event_diff(self, client) -> None:
        _make_user()
        _post_login(client)
        client.post(reverse("manage:settings"), self._valid_payload())

        event = SettingsEvent.objects.latest("occurred_at")
        assert event.user.email == "owner@example.test"
        assert "public_site_name" in event.diff
        assert event.diff["public_site_name"]["new"] == "Brandon's Kitchen"

    def test_invalid_window_rejected_by_the_check_constraint(self, client) -> None:
        # settings_cutoff_before_window_start: same_day_cutoff must be
        # before default_window_start.
        _make_user()
        _post_login(client)
        payload = self._valid_payload()
        payload["same_day_cutoff"] = "17:00"  # after window_start (16:00) — invalid
        resp = client.post(reverse("manage:settings"), payload)
        assert resp.status_code == 200  # re-rendered with errors, not redirected
        assert not Settings.objects.filter(pk=1).exists()
