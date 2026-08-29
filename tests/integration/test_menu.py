"""Integration tests for core/menu.py (spec §7.3-§7.7, milestone 2)."""
from __future__ import annotations

import pytest

from core import menu as menu_queries
from core.models import DayDishAvailability, Dish

pytestmark = pytest.mark.django_db


def _dish(slug: str, category: str = "X", sort_order: int = 0, **overrides) -> Dish:
    defaults = dict(
        slug=slug, name=slug.upper(), category=category, sort_order=sort_order,
        price_cents=100, is_active_on_menu=True,
    )
    defaults.update(overrides)
    return Dish.objects.create(**defaults)


class TestActiveDishes:
    def test_excludes_inactive_and_archived(self, trading_day) -> None:
        from django.utils import timezone

        _dish("a")
        _dish("b", is_active_on_menu=False)
        _dish("c", archived_at=timezone.now())
        slugs = {d.slug for d in menu_queries.active_dishes()}
        assert slugs == {"a"}

    def test_ordered_by_category_then_sort_order(self) -> None:
        _dish("z2", category="B", sort_order=1)
        _dish("z1", category="B", sort_order=0)
        _dish("a1", category="A", sort_order=0)
        slugs = [d.slug for d in menu_queries.active_dishes()]
        assert slugs == ["a1", "z1", "z2"]


class TestDishesForDate:
    def test_absent_availability_row_means_available_uncapped(self, trading_day, dish) -> None:
        result = menu_queries.dishes_for_date(trading_day)
        assert len(result) == 1
        assert result[0].sold_out is False

    def test_is_available_false_marks_sold_out(self, trading_day, dish) -> None:
        DayDishAvailability.objects.create(trading_day=trading_day, dish=dish, is_available=False)
        result = menu_queries.dishes_for_date(trading_day)
        assert result[0].sold_out is True

    def test_max_units_reached_marks_sold_out(self, trading_day, dish, slot) -> None:
        from django.utils import timezone

        from core.models import Customer, Order, OrderLine, OrderStatus, PaymentMethod

        DayDishAvailability.objects.create(trading_day=trading_day, dish=dish, max_units=2)
        customer = Customer.objects.create(full_name="A B", mobile_e164="+27821234567")
        order = Order.objects.create(
            order_number="CT-260901-0001", public_token="x" * 22, source="website",
            customer=customer, customer_name_snapshot="A B",
            customer_mobile_snapshot="+27821234567",
            trading_day=trading_day, slot=slot, status=OrderStatus.AWAITING_EFT,
            payment_method=PaymentMethod.EFT, subtotal_cents=17000, total_cents=17000,
            hold_expires_at=timezone.now() + timezone.timedelta(minutes=30),
        )
        OrderLine.objects.create(
            order=order, dish=dish, dish_name_snapshot=dish.name,
            unit_price_cents_snapshot=8500, quantity=2, line_total_cents=17000,
        )
        result = menu_queries.dishes_for_date(trading_day)
        assert result[0].sold_out is True  # 2 used, max 2

    def test_max_units_not_yet_reached_stays_available(self, trading_day, dish, slot) -> None:
        from django.utils import timezone

        from core.models import Customer, Order, OrderLine, OrderStatus, PaymentMethod

        DayDishAvailability.objects.create(trading_day=trading_day, dish=dish, max_units=5)
        customer = Customer.objects.create(full_name="A B", mobile_e164="+27821234567")
        order = Order.objects.create(
            order_number="CT-260901-0001", public_token="x" * 22, source="website",
            customer=customer, customer_name_snapshot="A B",
            customer_mobile_snapshot="+27821234567",
            trading_day=trading_day, slot=slot, status=OrderStatus.AWAITING_EFT,
            payment_method=PaymentMethod.EFT, subtotal_cents=8500, total_cents=8500,
            hold_expires_at=timezone.now() + timezone.timedelta(minutes=30),
        )
        OrderLine.objects.create(
            order=order, dish=dish, dish_name_snapshot=dish.name,
            unit_price_cents_snapshot=8500, quantity=2, line_total_cents=17000,
        )
        result = menu_queries.dishes_for_date(trading_day)
        assert result[0].sold_out is False  # 2 used, max 5

    def test_cancelled_order_does_not_count_toward_max_units(self, trading_day, dish, slot) -> None:
        from core.models import Customer, Order, OrderLine, OrderStatus, PaymentMethod

        DayDishAvailability.objects.create(trading_day=trading_day, dish=dish, max_units=1)
        customer = Customer.objects.create(full_name="A B", mobile_e164="+27821234567")
        order = Order.objects.create(
            order_number="CT-260901-0001", public_token="x" * 22, source="website",
            customer=customer, customer_name_snapshot="A B",
            customer_mobile_snapshot="+27821234567",
            trading_day=trading_day, slot=slot, status=OrderStatus.CANCELLED,
            cancellation_reason="customer_request",
            payment_method=PaymentMethod.EFT, subtotal_cents=8500, total_cents=8500,
        )
        OrderLine.objects.create(
            order=order, dish=dish, dish_name_snapshot=dish.name,
            unit_price_cents_snapshot=8500, quantity=1, line_total_cents=8500,
        )
        result = menu_queries.dishes_for_date(trading_day)
        assert result[0].sold_out is False


class TestDishOptions:
    def test_required_and_optional_groups(self, dish_with_options) -> None:
        options = menu_queries.dish_options(dish_with_options)
        by_name = {o.name: o for o in options}
        assert by_name["Spice"].required is True
        assert [v.name for v in by_name["Spice"].values] == ["Mild", "Hot"]
        assert by_name["Extra cheese"].required is False
        assert by_name["Extra cheese"].values[0].price_delta_cents == 1500


class TestDishBySlug:
    def test_found(self, dish) -> None:
        assert menu_queries.dish_by_slug(dish.slug).pk == dish.pk

    def test_not_found(self) -> None:
        assert menu_queries.dish_by_slug("nope") is None


class TestCategoriesOrdered:
    def test_groups_preserving_first_appearance_order(self) -> None:
        dishes = [
            menu_queries.MenuDish(1, "a", "A", "", 100, "", [], "Cat B", False, []),
            menu_queries.MenuDish(2, "b", "B", "", 100, "", [], "Cat A", False, []),
            menu_queries.MenuDish(3, "c", "C", "", 100, "", [], "Cat B", False, []),
        ]
        grouped = menu_queries.categories_ordered(dishes)
        assert [name for name, _ in grouped] == ["Cat B", "Cat A"]
        assert [d.slug for d in grouped[0][1]] == ["a", "c"]
