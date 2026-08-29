from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("orders/<str:public_token>/", views.order, name="order"),
    path("checkout/", views.checkout, name="checkout"),
]
