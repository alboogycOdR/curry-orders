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
absent here as *paths* — real GET traffic to `/`, `/basket/`, etc. is
served by `urls_v2`'s own patterns (registered first in
`config.urls_v2_root`, so they win).

Bug found 2026-09-14: `staff/login.html` (and every other staff
template — `src/templates/base.html`'s nav, extended by all of them)
calls `{% url 'public:home' %}`/`public:order`/`public:basket`/
`public:account`/`public:help`/`public:policies`/`public:lookup`/
`public:order_status` (the last one from `staff/_inbox_section.html`,
each order row linking out to its public status page) for its shared
customer-facing chrome, unconditionally, on every page — staff pages
included. On the main deploy (`config.urls`) that's fine, `public.urls`
registers the full set. Here, before this fix, none of those names
existed under the "public" namespace at all (the docstring above only
ever scoped this file to JSON/media endpoints), so every staff page —
not just login, any page reachable after signing in too — 500'd with
`NoReverseMatch` the moment anyone tried to load it on this deploy.
Confirmed exhaustive by grepping every `{% url 'public:...' %}` (and
double-quoted/`reverse()` variants) across `src/templates/staff/` and
`base.html` — these eight names are the complete set. Staff `/manage/`
logic itself is untouched (root CLAUDE.md: "do not rewrite... staff
/manage/") — this only adds the missing *name* resolution
`{% url 'public:...' %}` needs, aliased to the equivalent `views_v2`
screen, exactly the aliasing technique `urls_v2.py`'s own docstring
already describes for `customer_logout`/OAuth. Real GET traffic to
these paths is still served entirely by `urls_v2`'s own patterns
(listed first) — these entries exist for `{% url %}` reversal only.
`order` has no direct v2 equivalent (the poster variant merged
Broadsheet's separate Order/Menu split into one Menu screen) — aliased
to `views_v2.menu`, the closest actual destination. `order_status`
reuses `views_v2.order_status` (the poster-styled tracker page,
`public_token` kwarg) rather than the Broadsheet one, matching every
other page on this deploy.
"""
from django.urls import path

from . import api, views, views_v2

app_name = "public"

urlpatterns = [
    path("api/checkout", api.checkout, name="api_checkout"),
    path("api/orders/<str:public_token>/proof", api.upload_proof, name="api_upload_proof"),
    path("api/availability", api.availability, name="api_availability"),
    path("api/order/day/<str:date_str>/", views.api_day_availability, name="api_day_availability"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("media/<path:key>", views.public_media, name="public_media"),
    # Name-only aliases so base.html's shared nav (staff pages included)
    # resolves `{% url 'public:...' %}` on this deploy — see this
    # module's own docstring above. Real requests to these paths never
    # reach these entries; urls_v2's own patterns are registered first.
    path("", views_v2.home, name="home"),
    path("menu/", views_v2.menu, name="order"),
    path("basket/", views_v2.basket, name="basket"),
    path("account/", views_v2.account, name="account"),
    path("help/", views_v2.help_page, name="help"),
    path("policies/", views_v2.policies_page, name="policies"),
    path("lookup/", views_v2.lookup, name="lookup"),
    path("orders/<str:public_token>/", views_v2.order_status, name="order_status"),
]
