"""Root URLconf.

Real routes (spec §6.1/§6.2) land with the milestones that build the
views behind them (menu, cart, checkout, EFT page, kitchen/collection
boards, ...). For now this only needs to (a) not crash
`python manage.py check` and (b) expose the exact namespaced URL names
the other agent's `src/templates/base.html` already has TODOs for:
`public:home`, `public:order`, `public:checkout`, `manage:kitchen`.

D-26: the staff app is served from the same origin under `/manage/` —
no separate host/CORS setup. The Python package behind that prefix is
named `staff`, not `manage` (see config/settings/base.py's STAFF_APP_NAME
comment for why); only the URL namespace is `manage`.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("manage/", include("staff.urls")),  # namespace "manage" (app_name in staff/urls.py)
    path("", include("public.urls")),  # namespace "public"
]
