from django.urls import path

from . import api, views

app_name = "manage"  # URL namespace stays "manage" (D-26) though the Python package is "staff"

urlpatterns = [
    # §12.2's staff landing page (M9) — "/manage/" root.
    path("", views.inbox, name="inbox"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("change-password/", views.change_password, name="change_password"),
    path("settings/", views.settings_view, name="settings"),
    path("calendar/", views.calendar, name="calendar"),
    path("orders/new/", views.assisted_order_new, name="assisted_order_new"),
    path("kitchen/", views.kitchen, name="kitchen"),
    path("collection/", views.collection_board, name="collection"),
    path("payments/", views.payments_queue, name="payments"),
    path("cash/", views.cash_requests, name="cash_requests"),
    # No-date-given nav entry point — redirects to today's own daily
    # controls page rather than needing a context processor just so
    # base.html's static {% url %} nav link can name "today".
    path("days/", views.daily_controls_today, name="daily_controls_today"),
    path("days/<str:date>/", views.daily_controls, name="daily_controls"),
    # §12.7 menu editor (M8 remainder).
    path("menu/", views.menu_list, name="menu_list"),
    path("menu/new/", views.dish_create, name="dish_create"),
    path("menu/<int:dish_id>/", views.dish_edit, name="dish_edit"),
    path("menu/<int:dish_id>/archive/", views.dish_archive, name="dish_archive"),
    path("menu/<int:dish_id>/unarchive/", views.dish_unarchive, name="dish_unarchive"),
    # §17.3's staff API contract — no trailing slash, same convention
    # public/urls.py's api_checkout uses (POST-only, so APPEND_SLASH's
    # GET/HEAD-only redirect would just 404 a slashed-vs-not mismatch).
    path("api/orders/<int:order_id>/transition", api.transition, name="api_transition"),
    path("api/orders/<int:order_id>/assign", api.assign_order, name="api_assign_order"),
    path("api/days/<str:date>/lock-kitchen", api.lock_prep_list, name="api_lock_prep_list"),
    path("api/days/<str:date>/close-out", api.close_out_day, name="api_close_out_day"),
    path(
        "api/days/<str:date>/slots/<int:slot_id>/move-all",
        api.move_all_orders, name="api_move_all_orders",
    ),
]
