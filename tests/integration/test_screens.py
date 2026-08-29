"""Integration tests for the four Broadsheet screen templates (design
handoff: `updates/Curry orders modernization/design_handoff_brandons_kitchen/`).

These hit real views + templates against Postgres (pytest-django's `db`
fixture), unlike tests/unit — appropriate here since the views touch
`Settings.current()` and template rendering, not pure functions. Scope is
"does it render and wire together correctly", not pixel fidelity (that was
checked manually against the handoff's screenshots — see the session's
own notes, not something worth encoding as an assertion).
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from core.models import Settings

pytestmark = pytest.mark.django_db


class TestUrlNames:
    """The four names base.html's nav depends on, plus the real
    §6.1 order-status route kept separate from `public:order` (see
    public/urls.py's comment on why they're no longer the same name).
    """

    def test_all_four_screen_names_resolve(self) -> None:
        assert reverse("public:home") == "/"
        assert reverse("public:order") == "/order/"
        assert reverse("public:checkout") == "/checkout/"
        assert reverse("manage:kitchen") == "/manage/kitchen/"

    def test_order_status_route_is_distinct_from_order_screen(self) -> None:
        assert reverse("public:order_status", args=["tok123"]) == "/orders/tok123/"


class TestHome:
    def test_renders_with_no_settings_row(self, client) -> None:
        # Pre-seed: Settings.current() falls back to the model's own field
        # defaults (§7.2) rather than crashing on a missing row.
        resp = client.get(reverse("public:home"))
        assert resp.status_code == 200
        assert b"Brandon" in resp.content
        assert b"100" in resp.content  # default_daily_order_cap default

    def test_hero_figures_come_from_settings_when_seeded(self, client) -> None:
        Settings.objects.create(id=1, public_site_name="Brandon's Kitchen", default_daily_order_cap=24)
        resp = client.get(reverse("public:home"))
        assert resp.status_code == 200
        assert b">24<" in resp.content

    def test_todays_picks_present(self, client) -> None:
        resp = client.get(reverse("public:home"))
        content = resp.content.decode()
        for name in ("Full House Masala Steak Gatsby", "Chicken Masala Roti Roll", "Beef Lasagne"):
            assert name in content


class TestOrder:
    def test_renders_full_menu(self, client) -> None:
        resp = client.get(reverse("public:order"))
        assert resp.status_code == 200
        content = resp.content.decode()
        # One row per category letter (handoff README §2's table) and at
        # least one dish from each.
        for letter in ("A", "A3", "B", "C", "D"):
            assert f">{letter}<" in content
        assert "Full House Masala Steak Gatsby" in content
        assert "Portion to confirm" in content  # the one dish-level note

    def test_seven_day_picker_present(self, client) -> None:
        resp = client.get(reverse("public:order"))
        content = resp.content.decode()
        assert content.count('data-day-index="') == 7

    def test_menu_price_map_matches_sample_menu(self, client) -> None:
        from public import sample_menu

        resp = client.get(reverse("public:order"))
        content = resp.content.decode()
        for cat in sample_menu.MENU:
            for dish in cat.dishes:
                assert f'"{dish.id}"' in content
                assert str(dish.price) in content


class TestCheckout:
    def test_renders_form_and_confirmed_states(self, client) -> None:
        resp = client.get(reverse("public:checkout"))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert 'id="ck-form-state"' in content
        assert 'id="ck-confirmed-state"' in content
        assert "EFT before cooking" in content
        assert "Cash on collection" in content

    def test_days_data_present_for_checkout_js(self, client) -> None:
        resp = client.get(reverse("public:checkout"))
        content = resp.content.decode()
        assert 'id="days-data"' in content


class TestKitchen:
    def test_renders_run_sheet_and_meters(self, client) -> None:
        resp = client.get(reverse("manage:kitchen"))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Today's run" in content
        assert "1041" in content  # sample order ref
        assert "of 24 orders secured" in content

    def test_service_window_from_settings(self, client) -> None:
        from datetime import time

        Settings.objects.create(
            id=1,
            public_site_name="Brandon's Kitchen",
            default_window_start=time(16, 0),
            default_window_end=time(19, 30),
        )
        resp = client.get(reverse("manage:kitchen"))
        assert "16:00" in resp.content.decode()
        assert "19:30" in resp.content.decode()


class TestSettingsCurrent:
    """Settings.current() (core/models.py) — the D-24 singleton lookup
    every view in this pass relies on.
    """

    def test_returns_unsaved_defaults_pre_seed(self) -> None:
        # `Settings.id` itself defaults to 1 (D-24's CHECK needs it to),
        # so `pk` isn't a reliable saved/unsaved signal here — check
        # against the DB directly instead.
        assert not Settings.objects.filter(pk=1).exists()
        settings = Settings.current()
        assert settings.default_daily_order_cap == 100

    def test_returns_real_row_once_seeded(self) -> None:
        Settings.objects.create(id=1, public_site_name="Brandon's Kitchen", default_daily_order_cap=24)
        settings = Settings.current()
        assert settings.pk == 1
        assert settings.default_daily_order_cap == 24
