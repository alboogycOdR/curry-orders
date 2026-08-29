from django.urls import path

from . import api, views

app_name = "manage"  # URL namespace stays "manage" (D-26) though the Python package is "staff"

urlpatterns = [
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("change-password/", views.change_password, name="change_password"),
    path("settings/", views.settings_view, name="settings"),
    path("kitchen/", views.kitchen, name="kitchen"),
    path("collection/", views.collection_board, name="collection"),
    path("payments/", views.payments_queue, name="payments"),
    path("cash/", views.cash_requests, name="cash_requests"),
    # No-date-given nav entry point — redirects to today's own daily
    # controls page rather than needing a context processor just so
    # base.html's static {% url %} nav link can name "today".
    path("days/", views.daily_controls_today, name="daily_controls_today"),
    path("days/<str:date>/", views.daily_controls, name="daily_controls"),
    # §17.3's staff API contract — no trailing slash, same convention
    # public/urls.py's api_checkout uses (POST-only, so APPEND_SLASH's
    # GET/HEAD-only redirect would just 404 a slashed-vs-not mismatch).
    path("api/orders/<int:order_id>/transition", api.transition, name="api_transition"),
    path("api/days/<str:date>/lock-kitchen", api.lock_prep_list, name="api_lock_prep_list"),
    path("api/days/<str:date>/close-out", api.close_out_day, name="api_close_out_day"),
    path(
        "api/days/<str:date>/slots/<int:slot_id>/move-all",
        api.move_all_orders, name="api_move_all_orders",
    ),
]
