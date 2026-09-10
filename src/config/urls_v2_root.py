"""Root URLconf for the poster-variant standalone deploy — docker-compose's
`web-v2` service (its own port), same image and database as `web`,
selected via `ROOT_URLCONF=config.urls_v2_root` in that service's
environment (see config/settings/base.py and docker-compose.yml).

Why a separate urlconf instead of the `/v2/` prefix in config/urls.py:
serving the poster variant at "/" of its own port, rather than under a
path prefix on the shared port, avoids prefix-relative quirks entirely
(observed live: some in-page navigation behaved as if still scoped to
`/v2/`) and gives Brandon two plain, independent URLs to compare rather
than one site with a sub-path. Both still run the exact same code and
share the same database; only which urlconf is mounted at "/" differs.

`public.urls_v2` (namespace "v2") claims "", "checkout/",
"orders/<token>/" and "lookup/" — this deploy always serves the poster
variant's own version of those. The rest of this file hand-picks the
specific `public.views`/`public.api` endpoints the poster templates
actually call (`{% url 'public:account' %}`, `api_checkout`, etc.)
rather than `include("public.urls")` wholesale: that would also expose
`/menu/`, `/order/`, `/basket/` and `/dishes/<slug>/` — real, working,
but rendered in the *Broadsheet* style and reachable by nobody except
someone typing the URL directly, since nothing in the poster UI links
to them. Leaving them out means every reachable page on this deploy is
actually poster-styled — the "no broken/inconsistent links" bar the
2025-09 audit set (see the commit this file was written in).
"""
from django.contrib import admin
from django.urls import include, path

from jobs.views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz, name="healthz"),
    path("manage/", include("staff.urls")),  # namespace "manage" — staff still reachable
    path("", include("public.urls_v2")),  # namespace "v2" — home/checkout/order_status/lookup
    # namespace "public" — hand-picked subset; see public/urls_v2_supplement.py's docstring.
    path("", include("public.urls_v2_supplement")),
]
