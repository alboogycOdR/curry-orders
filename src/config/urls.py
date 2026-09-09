"""Root URLconf.

The four Broadsheet screen templates (`public:home`, `public:order`,
`public:checkout`, `manage:kitchen`) are real views now — see
`public/urls.py` and `staff/urls.py`. Staff auth (`manage:login`,
`manage:logout`, `manage:change_password`) and the owner-only
`manage:settings` editor round out milestone 1 (spec §22 row 1), along
with `/healthz` below. Everything else in spec §6.1/§6.2 (the EFT page,
staff inbox/payments/collection boards, ...) still lands with the
milestone that builds it.

D-26: the staff app is served from the same origin under `/manage/` —
no separate host/CORS setup. The Python package behind that prefix is
named `staff`, not `manage` (see config/settings/base.py's STAFF_APP_NAME
comment for why); only the URL namespace is `manage`.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from jobs.views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    # Ops endpoint (§17.1/RUNBOOK.md), not namespaced under public/manage
    # — a load balancer or uptime check hits this directly.
    path("healthz", healthz, name="healthz"),
    path("manage/", include("staff.urls")),  # namespace "manage" (app_name in staff/urls.py)
    # Poster-variant comparison surface (updates0909/handover_poster_variant)
    # — runs side by side with the surface below at "", not a replacement
    # of it, until one is chosen and the other archived. Must come before
    # the public include below so /v2/... doesn't fall through to
    # public.urls' "" pattern first.
    path("v2/", include("public.urls_v2")),  # namespace "v2"
    path("", include("public.urls")),  # namespace "public"
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
