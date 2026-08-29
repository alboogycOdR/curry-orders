# Media handling: signed URLs, upload validation (magic-byte check, size
# cap, random storage key — spec §7.13/§15/§18.17), django-storages/MinIO
# wiring. No models of its own — core.Media (core/models.py) is the DB
# table; this app will hold the behaviour around it. Out of scope for this
# milestone (models only).
