from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    # The handoff's "Order" screen (menu + day/slot picker + cart) — plain
    # URL, no token, since it's a nav destination (base.html's "Order"
    # link). Spec §6.1 actually splits this into /menu and /cart; the
    # handoff deliberately merges them into one screen for now (README:
    # "the four screens are separate URLs"). Revisit the split if/when
    # /menu grows real per-dish permalinks (§6.1 "Dish detail... used in
    # WhatsApp Status, Instagram, TikTok") that this single route can't serve.
    path("order/", views.order, name="order"),
    path("checkout/", views.checkout, name="checkout"),
    # Spec §6.1's real `/orders/:public_token` (order status / EFT
    # instructions / confirmed view) — named `order_status` rather than
    # `order` to leave that name free for the screen above.
    path("orders/<str:public_token>/", views.order_status, name="order_status"),
]
