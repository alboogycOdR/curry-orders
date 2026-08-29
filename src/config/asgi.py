"""ASGI entrypoint. Not used by the gunicorn/WSGI deploy path in
docker-compose.yml (§17 chose gunicorn + HTMX polling over WebSockets),
but Django's standard project layout includes it, and it costs nothing to
keep available for a future async job or dev-server use.
"""
import os

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    f"config.settings.{os.environ.get('DJANGO_ENV', 'prod')}",
)

from django.core.asgi import get_asgi_application  # noqa: E402

application = get_asgi_application()
