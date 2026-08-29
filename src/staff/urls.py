from django.urls import path

from . import views

app_name = "manage"  # URL namespace stays "manage" (D-26) though the Python package is "staff"

urlpatterns = [
    path("kitchen/", views.kitchen, name="kitchen"),
]
