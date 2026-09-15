"""Staff-facing JSON API urlconf for the Flutter mobile app's staff mode
(docs/mobile/FLUTTER_APP_PLAN.md Phase 6). Sibling to
`public.urls_v1_api` (mounted the same way, at `/api/v1/staff/` instead
of `/api/v1/`) — kept as its own urlconf/module rather than folded into
`staff.urls` (the "manage" namespace, server-rendered HTML pages) so the
two surfaces (HTML boards for a browser, JSON for the app) stay visibly
separate the same way `public.urls`/`public.urls_v1_api` already are.

Action endpoints are NOT re-declared here — `staff.api.transition`/
`assign_order`/`lock_prep_list`/`close_out_day`/`move_all_orders`
already live at `/manage/api/...` (staff.urls) and are plain session
+CSRF-authed JSON already; the app calls those exact URLs directly.
This urlconf only adds the *read* endpoints (one per staff screen) and
auth (login/logout/me) that don't already exist as JSON anywhere.

View functions are split across several `api_mobile_*.py` modules
(rather than one large `api_mobile.py`) because Phase 6 was built as
several independent screens in parallel — one module per
independently-built group keeps two agents from ever editing the same
file at once. `api_mobile.py` itself holds only auth + the shared
`staff_login_required_json`/`_error_response` helpers every other
module imports from it.
"""
from django.urls import path

from . import (
    api_mobile,
    api_mobile_admin,
    api_mobile_assisted_order,
    api_mobile_boards,
    api_mobile_collection_cash,
    api_mobile_daily_controls,
    api_mobile_menu,
    api_mobile_payments,
)

app_name = "api_v1_staff"

urlpatterns = [
    path("auth/login/", api_mobile.login_json, name="login"),
    path("auth/logout/", api_mobile.logout_json, name="logout"),
    path("auth/me/", api_mobile.me_json, name="me"),
    path("inbox/", api_mobile_boards.inbox_json, name="inbox"),
    path("kitchen/", api_mobile_boards.kitchen_json, name="kitchen"),
    path("collection/", api_mobile_collection_cash.collection_json, name="collection"),
    path("cash/", api_mobile_collection_cash.cash_json, name="cash"),
    path("payments/", api_mobile_payments.payments_json, name="payments"),
    path("calendar/", api_mobile_payments.calendar_json, name="calendar"),
    path("days/<str:date>/", api_mobile_daily_controls.daily_controls_json, name="daily_controls"),
    path("menu/", api_mobile_menu.menu_list_json, name="menu_list"),
    path("menu/new/", api_mobile_menu.dish_create_json, name="dish_create"),
    path("menu/<int:dish_id>/", api_mobile_menu.dish_detail_json, name="dish_detail"),
    path(
        "menu/<int:dish_id>/image/", api_mobile_menu.dish_image_upload_json, name="dish_image_upload",
    ),
    path("menu/<int:dish_id>/archive/", api_mobile_menu.dish_archive_json, name="dish_archive"),
    path("menu/<int:dish_id>/unarchive/", api_mobile_menu.dish_unarchive_json, name="dish_unarchive"),
    path(
        "menu/<int:dish_id>/options/",
        api_mobile_menu.dish_option_create_json, name="dish_option_create",
    ),
    path(
        "menu/<int:dish_id>/options/<int:option_id>/",
        api_mobile_menu.dish_option_detail_json, name="dish_option_detail",
    ),
    path(
        "menu/<int:dish_id>/options/<int:option_id>/values/",
        api_mobile_menu.dish_option_value_create_json, name="dish_option_value_create",
    ),
    path(
        "menu/<int:dish_id>/options/<int:option_id>/values/<int:value_id>/",
        api_mobile_menu.dish_option_value_detail_json, name="dish_option_value_detail",
    ),
    path("orders/new/", api_mobile_assisted_order.assisted_order_json, name="assisted_order"),
    path("settings/", api_mobile_admin.settings_json, name="settings"),
    path("team/", api_mobile_admin.team_json, name="team"),
    path("team/<int:allowlist_id>/", api_mobile_admin.team_member_json, name="team_member"),
]
