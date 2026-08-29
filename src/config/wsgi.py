"""WSGI entrypoint — `gunicorn config.wsgi:application` (docker-compose.yml).

Defaults `DJANGO_ENV` to `prod` (unlike manage.py, which defaults to `dev`)
because this module is the production/container entrypoint; set
`DJANGO_SETTINGS_MODULE` explicitly to override.
"""
import os

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    f"config.settings.{os.environ.get('DJANGO_ENV', 'prod')}",
)

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
