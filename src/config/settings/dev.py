"""Local development settings."""
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Verbose SQL/errors are fine locally; nothing security-sensitive here.
