"""Email magic-link token creation and sending."""
import secrets
import datetime as dt

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from core.models import LoginToken


TOKEN_BYTES = 48  # 64-char base64url token


def create_token(email: str, intent: str) -> str:
    """Create a one-time LoginToken and return the raw token string.
    intent must be 'staff' or 'customer'.
    Expires in settings.MAGIC_LINK_EXPIRY_MINUTES minutes.
    """
    token = secrets.token_urlsafe(TOKEN_BYTES)
    expires = timezone.now() + dt.timedelta(minutes=getattr(settings, "MAGIC_LINK_EXPIRY_MINUTES", 15))
    LoginToken.objects.create(
        token=token,
        email=email,
        intent=intent,
        expires_at=expires,
    )
    return token


def send_magic_link(email: str, intent: str, site_url: str, callback_url_name: str) -> None:
    """Create a token and email the magic link to the user.
    callback_url_name: full URL path (not a URL name) — e.g. '/manage/auth/email/callback/'.
    """
    token = create_token(email, intent)
    link = site_url.rstrip("/") + callback_url_name + "?t=" + token
    subject = "Your sign-in link"
    body = (
        f"Click the link below to sign in (valid for {getattr(settings, 'MAGIC_LINK_EXPIRY_MINUTES', 15)} minutes):\n\n"
        f"{link}\n\n"
        "If you did not request this, you can safely ignore it."
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)


def consume_token(token_str: str, intent: str):
    """Validate and consume a LoginToken. Returns the LoginToken on success,
    raises ValueError with a user-facing message on any failure.
    """
    now = timezone.now()
    try:
        tok = LoginToken.objects.get(token=token_str, intent=intent)
    except LoginToken.DoesNotExist:
        raise ValueError("This sign-in link is invalid or has already been used.")
    if tok.used_at is not None:
        raise ValueError("This sign-in link has already been used.")
    if tok.expires_at < now:
        raise ValueError("This sign-in link has expired. Request a new one.")
    tok.used_at = now
    tok.save(update_fields=["used_at"])
    return tok
