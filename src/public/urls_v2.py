"""Poster-variant URLs, mounted at /v2/ in config/urls.py (namespace "v2").

Separate from public/urls.py's "public" namespace deliberately — the two
customer surfaces run side by side (updates0909/handover_poster_variant/
README.md's "run both live, archive the loser" decision) rather than one
replacing the other, so each needs its own route table even while both
call into the same views.py helpers underneath.
"""
from django.urls import path

from . import views_v2

app_name = "v2"

urlpatterns = [
    path("", views_v2.home, name="home"),
    path("menu/", views_v2.menu, name="menu"),
    path("checkout/", views_v2.checkout, name="checkout"),
    path("orders/<str:public_token>/", views_v2.order_status, name="order_status"),
    path("lookup/", views_v2.lookup, name="lookup"),
]
