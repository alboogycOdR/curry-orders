"""Poster-variant URLs (namespace "v2"), mounted at "/" of its own
standalone deploy — docker-compose's web-v2 service, config/urls_v2_root.py.

Native ownership of the full customer-facing information architecture,
matching public/urls.py's own (2025-09 IA-alignment review): Home, Menu
(the interactive add-to-cart screen — public/order.js's real behaviour,
not the crawlable read-only /menu/), Basket (its own page, day/slot
picker + line review + Continue — not the drawer an earlier build of
this variant used), Checkout, order status, lookup, and the full
Account family (hub, login, signup, setup, logout, Google OAuth).

Login/logout/OAuth need no poster-specific view at all: `customer_logout`/
`customer_google_begin`/`customer_google_callback` only ever redirect by
name (`redirect("public:account")` etc.) — since this urlconf registers
those same names as aliases to these exact v2 views (see
public/urls_v2_supplement.py), the redirect's URL *text* comes out
identical on both deploys, and the follow-up request naturally lands on
whichever view is registered for that path on *this* urlconf (these v2
patterns, listed before the supplement's). No parametrisation needed for
those three; `views_v2.customer_login`/`customer_signup`/`account_setup`
exist only because those three *render a template*, which does differ.

Everything views.py exposes that isn't part of this customer-facing
surface (the crawlable-only /menu/, /order/'s Broadsheet twin, /dishes/
permalinks) is deliberately not reachable here — see
public/urls_v2_supplement.py's own docstring.
"""
from django.urls import path

from . import views as public_views
from . import views_v2

app_name = "v2"

urlpatterns = [
    path("", views_v2.home, name="home"),
    path("menu/", views_v2.menu, name="menu"),
    path("basket/", views_v2.basket, name="basket"),
    path("checkout/", views_v2.checkout, name="checkout"),
    path("orders/<str:public_token>/", views_v2.order_status, name="order_status"),
    path("lookup/", views_v2.lookup, name="lookup"),
    path("account/", views_v2.account, name="account"),
    path("account/login/", views_v2.customer_login, name="customer_login"),
    path("account/signup/", views_v2.customer_signup, name="customer_signup"),
    path("account/logout/", public_views.customer_logout, name="customer_logout"),
    path("account/auth/google/", public_views.customer_google_begin, name="customer_google_begin"),
    path(
        "account/auth/google/callback/",
        public_views.customer_google_callback,
        name="customer_google_callback",
    ),
    path("account/setup/", views_v2.account_setup, name="account_setup"),
    path("orders/<str:public_token>/reorder/", views_v2.reorder, name="reorder"),
    path("help/", views_v2.help_page, name="help"),
    path("policies/", views_v2.policies_page, name="policies"),
]
