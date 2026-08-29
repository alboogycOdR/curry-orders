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

from core.models import Dish, Settings

pytestmark = pytest.mark.django_db


def _make_dish(slug: str, name: str, category: str, price_cents: int = 8500, **overrides) -> Dish:
    defaults = dict(
        slug=slug, name=name, category=category, price_cents=price_cents,
        is_active_on_menu=True,
    )
    defaults.update(overrides)
    return Dish.objects.create(**defaults)


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
        Settings.objects.create(
            id=1, public_site_name="Brandon's Kitchen", default_daily_order_cap=24
        )
        resp = client.get(reverse("public:home"))
        assert resp.status_code == 200
        assert b">24<" in resp.content

    def test_todays_picks_present_when_seeded(self, client) -> None:
        _make_dish("full-house-masala-steak-gatsby", "Full House Masala Steak Gatsby", "Gatsby")
        _make_dish("chicken-masala-roti-roll", "Chicken Masala Roti Roll", "Masala Roti Rolls")
        _make_dish("beef-lasagne", "Beef Lasagne", "Italian Lasagne")
        resp = client.get(reverse("public:home"))
        content = resp.content.decode()
        for name in ("Full House Masala Steak Gatsby", "Chicken Masala Roti Roll", "Beef Lasagne"):
            assert name in content

    def test_no_picks_section_crash_pre_seed(self, client) -> None:
        # No dishes at all yet — home() must not 500 on an empty picks list.
        resp = client.get(reverse("public:home"))
        assert resp.status_code == 200


class TestOrder:
    def test_renders_seeded_menu_grouped_by_category(self, client) -> None:
        _make_dish("chicken-curry-roti", "Chicken Curry & Roti", "Roti & Curry", 8500)
        _make_dish("steak-curry-roti", "Steak Curry & Roti", "Roti & Curry", 9500)
        _make_dish("beef-lasagne", "Beef Lasagne", "Italian Lasagne", 9000)
        resp = client.get(reverse("public:order"))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Roti &amp; Curry" in content or "Roti & Curry" in content
        assert "Chicken Curry &amp; Roti" in content or "Chicken Curry & Roti" in content
        assert "Steak Curry &amp; Roti" in content or "Steak Curry & Roti" in content
        assert "Beef Lasagne" in content
        assert "R 85.00" in content

    def test_sold_out_dish_shows_sold_out_not_add(self, client, biz_settings) -> None:
        # Whichever date the order screen resolves as "soonest orderable"
        # (today itself only if still before the cut-off — depends on
        # wall-clock time, not something to assume in a test) — computed
        # here the same way public.views._orderable_day_list does, not
        # duplicated/guessed, so this stays correct at any time of day.
        from core.materialise import materialise_days
        from core.models import DayDishAvailability
        from core.tz import now_sast, orderable_dates

        today = now_sast().date()
        horizon_count = biz_settings.preorder_days + 1
        days_list = materialise_days(today, biz_settings, count=horizon_count)
        trading_days = {td.date: td for td in days_list}
        first_date = orderable_dates(
            now_sast(),
            is_open=lambda d: trading_days[d].is_open if d in trading_days else False,
            cutoff_time=trading_days[today].cutoff_time,
            preorder_days=biz_settings.preorder_days,
        )[0]

        dish = _make_dish("chicken-curry-roti", "Chicken Curry & Roti", "Roti & Curry")
        DayDishAvailability.objects.create(
            trading_day=trading_days[first_date], dish=dish, is_available=False
        )
        resp = client.get(reverse("public:order"))
        content = resp.content.decode()
        assert 'class="op-dish-row is-sold-out"' in content
        assert '<span class="tag tag-neutral">Sold out</span>' in content

    def test_day_picker_present_within_horizon(self, client) -> None:
        resp = client.get(reverse("public:order"))
        content = resp.content.decode()
        # today (if before cut-off) + up to 7 more days (D-05) — 7 or 8
        # depending on the wall-clock time this test happens to run at
        # relative to the default 10:00 SAST cut-off, not something to
        # pin to a single number without mocking the clock.
        count = content.count('data-day-index="')
        assert 7 <= count <= 8

    def test_dish_price_rendered_via_cents_filter(self, client) -> None:
        _make_dish("chicken-curry-roti", "Chicken Curry & Roti", "Roti & Curry", 8500)
        resp = client.get(reverse("public:order"))
        content = resp.content.decode()
        assert "R 85.00" in content


class TestMenuPage:
    def test_renders_and_links_to_dish_detail(self, client) -> None:
        _make_dish("chicken-curry-roti", "Chicken Curry & Roti", "Roti & Curry", 8500)
        resp = client.get(reverse("public:menu"))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Chicken Curry" in content
        assert reverse("public:dish_detail", args=["chicken-curry-roti"]) in content

    def test_date_param_outside_horizon_falls_back(self, client) -> None:
        resp = client.get(reverse("public:menu"), {"date": "2099-01-01"})
        assert resp.status_code == 200


class TestDishDetail:
    def test_renders_dish_with_options(self, client, dish_with_options) -> None:
        resp = client.get(reverse("public:dish_detail", args=[dish_with_options.slug]))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert dish_with_options.name in content
        assert "Spice" in content
        assert "Mild" in content
        assert "Extra cheese" in content

    def test_unknown_slug_is_404(self, client) -> None:
        resp = client.get(reverse("public:dish_detail", args=["no-such-dish"]))
        assert resp.status_code == 404

    def test_archived_dish_is_404(self, client) -> None:
        from django.utils import timezone

        dish = _make_dish("old-dish", "Old Dish", "Roti & Curry", archived_at=timezone.now())
        resp = client.get(reverse("public:dish_detail", args=[dish.slug]))
        assert resp.status_code == 404

    def test_date_outside_horizon_is_clamped_not_500(self, client) -> None:
        dish = _make_dish("chicken-curry-roti", "Chicken Curry & Roti", "Roti & Curry")
        resp = client.get(reverse("public:dish_detail", args=[dish.slug]), {"date": "2099-01-01"})
        assert resp.status_code == 200


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
    """Now behind `@staff_login_required` (staff/decorators.py) — see
    tests/integration/test_staff_auth_views.py for the gating itself
    (anonymous redirect, role checks, ...); these log in first since
    they're about the screen's content, not the gate.
    """

    def _login(self, client) -> None:
        from core.auth import hash_password
        from core.models import User, UserRole

        User.objects.create(
            email="owner@example.test",
            name="Owner",
            role=UserRole.OWNER,
            password_hash=hash_password("correct horse battery staple"),
            must_change_password=False,
        )
        client.post(
            reverse("manage:login"),
            {"email": "owner@example.test", "password": "correct horse battery staple"},
        )

    def test_renders_run_sheet_and_meters(self, client) -> None:
        self._login(client)
        resp = client.get(reverse("manage:kitchen"))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Today's run" in content
        assert "1041" in content  # sample order ref
        assert "of 24 orders secured" in content

    def test_service_window_from_settings(self, client) -> None:
        from datetime import time

        self._login(client)
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
        Settings.objects.create(
            id=1, public_site_name="Brandon's Kitchen", default_daily_order_cap=24
        )
        settings = Settings.current()
        assert settings.pk == 1
        assert settings.default_daily_order_cap == 24
