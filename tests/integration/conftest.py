"""Shared fixtures for integration tests that need a working trading
day/slot/dish setup — the capacity engine tests especially. Named
`biz_settings` (not `settings`) to avoid shadowing pytest-django's own
`settings` fixture (Django settings overrides), which is unrelated to
`core.models.Settings`.
"""
from __future__ import annotations

import datetime as dt

import pytest

from core.models import (
    Dish,
    DishOption,
    DishOptionValue,
    Settings,
    Slot,
    TradingDay,
    User,
    UserRole,
)


@pytest.fixture
def biz_settings(db) -> Settings:
    return Settings.objects.create(id=1, public_site_name="Brandon's Kitchen (test)")


@pytest.fixture
def trading_day(db) -> TradingDay:
    return TradingDay.objects.create(
        date=dt.date(2026, 9, 1),
        is_open=True,
        window_start=dt.time(16, 0),
        window_end=dt.time(18, 0),
        cutoff_time=dt.time(10, 0),
        daily_order_cap=100,
    )


@pytest.fixture
def slot(trading_day) -> Slot:
    return Slot.objects.create(
        trading_day=trading_day, start_at=dt.time(16, 0), end_at=dt.time(16, 15), capacity=13
    )


@pytest.fixture
def staff_user(db) -> User:
    return User.objects.create(
        email="manager@example.test", name="Test Manager", role=UserRole.MANAGER,
        password_hash="unused-in-these-tests",
    )


@pytest.fixture
def owner_user(db) -> User:
    return User.objects.create(
        email="owner@example.test", name="Test Owner", role=UserRole.OWNER,
        password_hash="unused-in-these-tests",
    )


@pytest.fixture
def dish(db) -> Dish:
    return Dish.objects.create(
        slug="chicken-curry-roti",
        name="Chicken Curry & Roti",
        price_cents=8500,
        category="Roti & Curry",
        is_active_on_menu=True,
    )


@pytest.fixture
def dish_with_options(db) -> Dish:
    dish = Dish.objects.create(
        slug="full-house-gatsby",
        name="Full House Masala Steak Gatsby",
        price_cents=13000,
        category="Gatsby",
        is_active_on_menu=True,
    )
    spice = DishOption.objects.create(dish=dish, name="Spice", required=True)
    DishOptionValue.objects.create(option=spice, name="Mild", price_delta_cents=0, sort_order=0)
    DishOptionValue.objects.create(option=spice, name="Hot", price_delta_cents=0, sort_order=1)
    extra = DishOption.objects.create(dish=dish, name="Extra cheese", required=False)
    DishOptionValue.objects.create(option=extra, name="Yes", price_delta_cents=1500)
    return dish
