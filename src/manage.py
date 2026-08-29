#!/usr/bin/env python
"""Django's command-line utility for administrative tasks.

Settings module selection: `DJANGO_SETTINGS_MODULE` wins if already set
(this is how pytest picks `config.settings.test` — see pyproject.toml's
`[tool.pytest.ini_options]`). Otherwise it is derived from `DJANGO_ENV`
(`dev` / `prod` / `test`, Appendix D), defaulting to `dev` for everyday
`manage.py runserver` / `migrate` use on a developer machine.
"""
import os
import sys


def main() -> None:
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        f"config.settings.{os.environ.get('DJANGO_ENV', 'dev')}",
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
