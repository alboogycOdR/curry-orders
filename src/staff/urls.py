from django.urls import path

from . import views

app_name = "manage"  # URL namespace stays "manage" (D-26) though the Python package is "staff"

urlpatterns = [
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("change-password/", views.change_password, name="change_password"),
    path("settings/", views.settings_view, name="settings"),
    path("kitchen/", views.kitchen, name="kitchen"),
]
