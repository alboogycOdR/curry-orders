"""Integration tests for the /help and /policies pages (spec §6.1/§11.12,
milestone 10's thin Phase 1 slice). `public/views.py::help_page`/
`policies_page`.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestHelpPage:
    def test_renders_live_settings_values(self, client, biz_settings) -> None:
        biz_settings.same_day_cutoff = "09:30"
        biz_settings.preorder_days = 5
        biz_settings.slot_minutes = 20
        biz_settings.eft_hold_minutes = 45
        biz_settings.save()
        resp = client.get(reverse("public:help"))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "09:30" in content
        assert "5 days" in content
        assert "20-minute" in content
        assert "45 minutes" in content

    def test_cash_section_reflects_disabled_cash(self, client, biz_settings) -> None:
        biz_settings.cash_enabled = False
        biz_settings.save()
        resp = client.get(reverse("public:help"))
        content = resp.content.decode()
        assert "not currently accepted" in content

    def test_cash_section_reflects_enabled_cash(self, client, biz_settings) -> None:
        biz_settings.cash_enabled = True
        biz_settings.cash_same_day_only = True
        biz_settings.save()
        resp = client.get(reverse("public:help"))
        content = resp.content.decode()
        assert "same-day orders only" in content

    def test_links_to_policies(self, client, biz_settings) -> None:
        resp = client.get(reverse("public:help"))
        assert reverse("public:policies").encode() in resp.content


class TestPoliciesPage:
    def test_renders_without_owner_wording_with_fallback(self, client, biz_settings) -> None:
        assert not biz_settings.allergen_disclaimer
        assert not biz_settings.home_kitchen_notice
        resp = client.get(reverse("public:policies"))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "not yet been provided" in content

    def test_renders_owner_wording_when_set(self, client, biz_settings) -> None:
        biz_settings.allergen_disclaimer = "Made in a kitchen that also handles nuts."
        biz_settings.home_kitchen_notice = "Prepared in a registered home kitchen."
        biz_settings.save()
        resp = client.get(reverse("public:policies"))
        content = resp.content.decode()
        assert "Made in a kitchen that also handles nuts." in content
        assert "Prepared in a registered home kitchen." in content
        assert "not yet been provided" not in content

    def test_includes_popia_and_retention_figures(self, client, biz_settings) -> None:
        biz_settings.proof_retention_days = 90
        biz_settings.order_retention_months = 18
        biz_settings.save()
        resp = client.get(reverse("public:policies"))
        content = resp.content.decode()
        assert "POPIA" in content
        assert "Finland" in content
        assert "90 days" in content
        assert "18 months" in content
        assert "Please don't place routine orders on WhatsApp" in content

    def test_whatsapp_link_when_configured(self, client, biz_settings) -> None:
        biz_settings.support_whatsapp_e164 = "+27821234567"
        biz_settings.save()
        resp = client.get(reverse("public:policies"))
        assert b"wa.me/27821234567" in resp.content

    def test_no_whatsapp_link_when_unconfigured(self, client, biz_settings) -> None:
        biz_settings.support_whatsapp_e164 = None
        biz_settings.save()
        resp = client.get(reverse("public:policies"))
        assert b"wa.me/" not in resp.content


class TestFooterLinks:
    def test_footer_present_on_home(self, client, biz_settings) -> None:
        resp = client.get(reverse("public:home"))
        content = resp.content.decode()
        assert 'href="/help/"' in content
        assert 'href="/policies/"' in content


class TestCheckoutPolicyLink:
    def test_checkout_links_to_policies(self, client, biz_settings) -> None:
        resp = client.get(reverse("public:checkout"))
        assert reverse("public:policies").encode() in resp.content
