"""Mobile app JSON API — the Flutter Android client
(docs/mobile/FLUTTER_APP_PLAN.md Phase 1). Mounted only on the
poster-variant deploy (config/urls_v2_root.py) at `/api/v1/`, matching
`mobile/lib/data/api_client.dart`'s base URL — same image/database as
the main site, just the one port the app talks to.

Every POST here needs the `csrftoken` cookie first (`GET csrf/`, session
auth otherwise unchanged from the web) — see `public.api`'s own "Flutter
app (Phase 1)" section for the full mechanism. `checkout/`/`availability/`
below are the exact same view functions `public.urls_v2_supplement`
exposes at the unversioned `api/...` paths; this module just re-exposes
them under a versioned prefix a mobile client can treat as stable,
without duplicating any logic.
"""
from django.urls import path

from . import api

app_name = "api_v1"

urlpatterns = [
    path("csrf/", api.csrf_cookie, name="csrf"),
    path("days/", api.orderable_days_json, name="days"),
    path("featured/", api.featured, name="featured"),
    path("availability/", api.availability, name="availability"),
    path("checkout/", api.checkout, name="checkout"),
    path("orders/<str:public_token>/", api.order_status_json, name="order_status"),
    path("orders/<str:public_token>/proof/", api.upload_proof, name="upload_proof"),
    path("orders/<str:public_token>/reorder/", api.reorder_json, name="reorder"),
    path("lookup/", api.lookup_json, name="lookup"),
    path("auth/login/", api.login_json, name="login"),
    path("auth/signup/", api.signup_json, name="signup"),
    path("auth/logout/", api.logout_json, name="logout"),
    path("account/", api.account_json, name="account"),
    path("account/orders/", api.account_orders_json, name="account_orders"),
]
