# Staff dashboard views live here (spec §6.2: inbox, payments, kitchen,
# collection, calendar, order detail, menu editor, daily controls,
# settings, reports, staff admin). No models of its own — the domain
# model is centralised in core/models.py. Python package name is `staff`,
# not `manage` — see config/settings/base.py's STAFF_APP_NAME comment.
# URL namespace stays "manage" (config/urls.py, staff/urls.py).
