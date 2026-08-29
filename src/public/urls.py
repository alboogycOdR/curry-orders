from django.urls import path

from . import api, views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    # §17.3's API contract — no trailing slash, matching the spec exactly
    # (and Django's APPEND_SLASH redirect only fires for GET/HEAD, not
    # POST, so a slashed-vs-not mismatch here would just 404 the client).
    path("api/checkout", api.checkout, name="api_checkout"),
    path("api/orders/<str:public_token>/proof", api.upload_proof, name="api_upload_proof"),
    # Spec §6.1's real per-dish permalink now exists (milestone 2), which
    # is exactly the trigger docs/DECISIONS.md D-32 named for revisiting
    # the /menu-vs-/order split — not revisited yet: /menu is the
    # crawlable browse page (§11.3), /order stays the handoff's single
    # interactive menu+cart+slot screen (§2's own framing, still true).
    path("menu/", views.menu, name="menu"),
    path("dishes/<slug:slug>/", views.dish_detail, name="dish_detail"),
    # The handoff's "Order" screen (menu + day/slot picker + cart) — plain
    # URL, no token, since it's a nav destination (base.html's "Order"
    # link).
    path("order/", views.order, name="order"),
    path("checkout/", views.checkout, name="checkout"),
    # Spec §6.1's real `/orders/:public_token` (order status / EFT
    # instructions / confirmed view) — named `order_status` rather than
    # `order` to leave that name free for the screen above.
    path("orders/<str:public_token>/", views.order_status, name="order_status"),
    # §6.1/§11.12 (milestone 10, Phase 1's own narrow slice of it — see
    # docs/DECISIONS.md).
    path("help/", views.help_page, name="help"),
    path("policies/", views.policies_page, name="policies"),
]
