"""Root URLconf.

The four Broadsheet screen templates (`public:home`, `public:order`,
`public:checkout`, `manage:kitchen`) are real views now — see
`public/urls.py` and `staff/urls.py`. Everything else in spec §6.1/§6.2
(the EFT page, staff inbox/payments/collection boards, ...) still lands
with the milestone that builds it.

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
