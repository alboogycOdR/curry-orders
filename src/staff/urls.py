from django.urls import path

from . import api, views

app_name = "manage"  # URL namespace stays "manage" (D-26) though the Python package is "staff"

urlpatterns = [
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("change-password/", views.change_password, name="change_password"),
    path("settings/", views.settings_view, name="settings"),
    path("kitchen/", views.kitchen, name="kitchen"),
    path("payments/", views.payments_queue, name="payments"),
    # §17.3's staff API contract — no trailing slash, same convention
    # public/urls.py's api_checkout uses (POST-only, so APPEND_SLASH's
    # GET/HEAD-only redirect would just 404 a slashed-vs-not mismatch).
    path("api/orders/<int:order_id>/transition", api.transition, name="api_transition"),
]
