"""The "public" namespace, as reachable from the poster-variant
standalone deploy (config/urls_v2_root.py) — trimmed to genuinely
cross-cutting things only: JSON API endpoints (called by JS, never
visited directly), the media proxy, and robots.txt.

Every real customer-facing screen (home, menu, basket, checkout, order
status, lookup, the full account family, reorder, help, policies) is
natively owned by public/urls_v2.py's own "v2" namespace, matching the
Broadsheet site's information architecture — see that module's
docstring for the 2025-09 review this followed. `/menu/`, `/order/`,
`/basket/`, `/dishes/<slug>/` (the Broadsheet-only pages this deploy
used to also expose, unstyled, before that review) are deliberately
absent here.
"""
from django.urls import path

from . import api, views

app_name = "public"

urlpatterns = [
    path("api/checkout", api.checkout, name="api_checkout"),
    path("api/orders/<str:public_token>/proof", api.upload_proof, name="api_upload_proof"),
    path("api/availability", api.availability, name="api_availability"),
    path("api/order/day/<str:date_str>/", views.api_day_availability, name="api_day_availability"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("media/<path:key>", views.public_media, name="public_media"),
]
