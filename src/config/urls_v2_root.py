"""Root URLconf for the poster-variant standalone deploy — docker-compose's
`web-v2` service (port 8104), same image and database as `web`, selected
via `ROOT_URLCONF=config.urls_v2_root` in that service's environment
(see config/settings/base.py and docker-compose.yml).

Why a separate urlconf instead of the `/v2/` prefix in config/urls.py:
serving the poster variant at "/" of its own port, rather than under a
path prefix on the shared port, avoids prefix-relative quirks entirely
(observed live: some in-page navigation behaved oddly under `/v2/`) and
gives Brandon two plain, independent URLs to compare —
`http://<host>:8102/` and `http://<host>:8104/` — rather than one site
with a sub-path. Both still run the exact same code and share the same
database; only which urlconf is mounted at "/" differs.

`public.urls_v2` (namespace "v2") is mounted first, at "/" — its own
top-level paths ("", "checkout/", "orders/<token>/", "lookup/") take
those exact URLs on this service. `public.urls` (namespace "public") is
included after: its *same-named* top-level paths are shadowed by the
v2 include above (intentional — this service always serves the poster
variant's checkout/orders/lookup), but everything public.urls defines
that v2 doesn't (account/, help/, policies/, api/*, media/,
orders/<token>/reorder/, dishes/<slug>/) still resolves normally, so
templates that reverse `public:account`, `public:help`,
`public:api_checkout`, etc. (base_v2.html, checkout.html) work
unchanged on this urlconf — Django's reverse() resolves against
whichever urlconf is actually mounted, so `{% url 'v2:home' %}` here
produces "/" instead of "/v2/" with no template edits required.
"""
from django.contrib import admin
from django.urls import include, path

from jobs.views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz, name="healthz"),
    path("manage/", include("staff.urls")),  # namespace "manage" — staff still reachable
    path("", include("public.urls_v2")),  # namespace "v2", now mounted at "/"
    path("", include("public.urls")),  # namespace "public" — non-overlapping paths only
]
