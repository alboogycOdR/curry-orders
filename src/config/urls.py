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
    path("", include("public.urls")),  # namespace "public"
]

# The poster-variant comparison surface (updates0909/handover_poster_variant)
# used to be mounted here at /v2/, but a path prefix under the same port
# caused enough in-page-navigation quirks (some links behaving as if
# still scoped to /v2/) that it moved to its own top-level deploy
# instead — docker-compose's `web-v2` service (port 8104), which reuses
# this exact codebase with a different ROOT_URLCONF
# (config.urls_v2_root mounts public.urls_v2 at "/" on that service).
# See that file's own comment for the full reasoning.

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
