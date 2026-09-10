"""The "public" namespace, as used by the poster-variant standalone
deploy (config/urls_v2_root.py) — a hand-picked subset of public/urls.py.

Deliberately excludes `menu/`, `order/`, `basket/` and `dishes/<slug>/`:
those pages exist and work, but only ever render in the *Broadsheet*
style, and nothing in the poster UI links to them. Leaving them out of
this deploy means every reachable page there is actually poster-styled
— see config/urls_v2_root.py's own docstring for the full reasoning.
Every pattern below is included precisely because some `{% url
'public:...' %}` call in a `templates/public/v2/*.html` or
`templates/base_v2.html` template needs it to resolve.
"""
from django.urls import path

from . import api, views
from . import views_v2

app_name = "public"

urlpatterns = [
    # Not duplicated business logic: these are the exact same views_v2
    # functions "v2:home"/"v2:lookup"/"v2:order_status" already point to,
    # at the exact same paths (see public/urls_v2.py) — registered again
    # under the "public" name only so account.html/help.html/
    # policies.html and the base.html chrome around them (unrestyled on
    # purpose, shared verbatim with the Broadsheet site — see this
    # deploy's own build notes) keep working: they call
    # `{% url 'public:home' %}`, `{% url 'public:lookup' %}`,
    # `{% url 'public:order_status' ... %}`, names that only exist in the
    # "v2" namespace once public.urls' full include was trimmed down.
    # Whichever name actually routes a given incoming request is
    # irrelevant — every alias below reaches the identical view either way.
    #
    # "basket"/"order" have no v2 equivalent page (basket is a drawer on
    # home; menu is a section of home) — both alias to v2's home view
    # too, same reasoning as home/lookup/order_status above.  A visitor
    # following one of these three from account/help/policies lands on
    # the real poster home page rather than a dead link; it just won't
    # already have the drawer open or be scrolled to the menu section.
    path("", views_v2.home, name="home"),
    path("basket/", views_v2.home, name="basket"),
    path("order/", views_v2.home, name="order"),
    path("lookup/", views_v2.lookup, name="lookup"),
    path("orders/<str:public_token>/", views_v2.order_status, name="order_status"),
    path("api/checkout", api.checkout, name="api_checkout"),
    path("api/orders/<str:public_token>/proof", api.upload_proof, name="api_upload_proof"),
    path("api/order/day/<str:date_str>/", views.api_day_availability, name="api_day_availability"),
    path("orders/<str:public_token>/reorder/", views.reorder, name="reorder"),
    path("account/", views.account, name="account"),
    path("account/login/", views.customer_login, name="customer_login"),
    path("account/signup/", views.customer_signup, name="customer_signup"),
    path("account/logout/", views.customer_logout, name="customer_logout"),
    path("account/auth/google/", views.customer_google_begin, name="customer_google_begin"),
    path(
        "account/auth/google/callback/",
        views.customer_google_callback,
        name="customer_google_callback",
    ),
    path("account/setup/", views.account_setup, name="account_setup"),
    path("help/", views.help_page, name="help"),
    path("policies/", views.policies_page, name="policies"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("media/<path:key>", views.public_media, name="public_media"),
]
