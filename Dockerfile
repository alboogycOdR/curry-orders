# Curry Takeaway Ordering System — image for the `web`/`scheduler`
# services in docker-compose.yml (§17.5). Both run this same image with
# different `command:`s (gunicorn vs `manage.py run_scheduler`).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# pyproject.toml + src/ only — deploy/, docs/, tests/, .env are all
# excluded via .dockerignore, keeping both the build context and the
# image itself free of anything that isn't runtime code.
COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir -e .

# Must be prod settings, not dev -- prod.py is the one with WhiteNoise's
# hashed-manifest storage backend (settings/prod.py), and that manifest
# file is exactly what this command generates. Needs no DB connection and
# no real secret (base.py's SECRET_KEY default is fine for this).
RUN DJANGO_SETTINGS_MODULE=config.settings.prod python src/manage.py collectstatic --noinput

# Runs as an unprivileged user — nothing here needs root, and the image
# runs on a box shared with other tenants (§17.5).
RUN useradd --system --create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app
USER app

WORKDIR /app/src
EXPOSE 8000
