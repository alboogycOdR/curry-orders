"""Minimal admin registration — every model gets a bare list_display so
`/admin/` doesn't 500 and staff data is inspectable. Not polished: no
custom forms, inlines, or search/filter tuning. That's later-milestone
work once the staff app has its own purpose-built screens (spec §12) and
this becomes a fallback/debug surface rather than the primary UI.
"""
from django.contrib import admin

from core.models import (
    Customer,
    DayDishAvailability,
    Dish,
    DishOption,
    DishOptionValue,
    IdempotencyKey,
    JobHeartbeat,
    Media,
    Order,
    OrderEvent,
    OrderLine,
    Payment,
    Settings,
    SettingsEvent,
    Slot,
    ThrottleEvent,
    TradingDay,
    User,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "role", "active", "must_change_password", "created_at")
    search_fields = ("email", "name")


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ("public_site_name", "cash_enabled", "vat_registered", "updated_at")


@admin.register(SettingsEvent)
class SettingsEventAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "occurred_at")


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "storage_key", "mime_type", "byte_size", "created_at")
    list_filter = ("kind",)


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "price_cents", "is_active_on_menu", "archived_at")
    search_fields = ("name", "slug")
    list_filter = ("is_active_on_menu", "category")


@admin.register(DishOption)
class DishOptionAdmin(admin.ModelAdmin):
    list_display = ("dish", "name", "required", "sort_order")


@admin.register(DishOptionValue)
class DishOptionValueAdmin(admin.ModelAdmin):
    list_display = ("option", "name", "price_delta_cents", "is_available")


@admin.register(TradingDay)
class TradingDayAdmin(admin.ModelAdmin):
    list_display = ("date", "is_open", "window_start", "window_end", "daily_order_cap")
    list_filter = ("is_open",)


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ("trading_day", "start_at", "end_at", "capacity", "is_closed")
    list_filter = ("is_closed",)


@admin.register(DayDishAvailability)
class DayDishAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("trading_day", "dish", "is_available", "max_units")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "mobile_e164", "order_count", "last_order_at")
    search_fields = ("full_name", "mobile_e164")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "status",
        "payment_method",
        "trading_day",
        "slot",
        "total_cents",
        "created_at",
    )
    list_filter = ("status", "payment_method", "source")
    search_fields = ("order_number", "customer_name_snapshot", "customer_mobile_snapshot")


@admin.register(OrderLine)
class OrderLineAdmin(admin.ModelAdmin):
    list_display = ("order", "dish_name_snapshot", "quantity", "option_key", "line_total_cents")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "method", "status", "amount_cents", "verified_at")
    list_filter = ("method", "status")


@admin.register(OrderEvent)
class OrderEventAdmin(admin.ModelAdmin):
    list_display = ("order", "from_status", "to_status", "action", "actor_kind", "occurred_at")
    list_filter = ("actor_kind",)


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("key", "order", "response_status", "created_at")


@admin.register(ThrottleEvent)
class ThrottleEventAdmin(admin.ModelAdmin):
    list_display = ("scope", "key", "occurred_at")
    list_filter = ("scope",)


@admin.register(JobHeartbeat)
class JobHeartbeatAdmin(admin.ModelAdmin):
    list_display = ("job_name", "last_run_at", "last_ok", "detail")
