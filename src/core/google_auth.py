"""Google OAuth2 helpers — reused by both the staff and public apps.

Keeps all Google-specific HTTP calls and state management in one place
so individual callback views stay thin.
"""
from __future__ import annotations

import secrets
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.http import HttpRequest

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
# The OIDC userinfo endpoint, not the legacy oauth2/v2/userinfo one — that
# older endpoint returns an "id" field, not "sub"; get_verified_google_user()
# below reads info["sub"], which KeyErrors against the v2 shape (silently,
# from the caller's point of view: the view's own `except Exception` catches
# it and just bounces back to the login page with no visible trace, since
# both the token exchange and this GET itself succeed — it's the field
# lookup afterward that fails). This endpoint returns `sub` per the OIDC
# spec, matching the "openid email profile" scope already requested.
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

_STATE_SESSION_KEY = "_google_oauth_state"


def get_redirect_uri(request: HttpRequest, callback_path: str) -> str:
    """Build the absolute callback URI from SITE_URL + callback_path."""
    return settings.SITE_URL.rstrip("/") + callback_path


def make_auth_url(redirect_uri: str, state: str) -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
    }
    return GOOGLE_AUTH_URL + "?" + urlencode(params)


def begin_google_login(request: HttpRequest, callback_path: str) -> str:
    """Store CSRF state in session and return the Google auth URL to redirect to."""
    state = secrets.token_urlsafe(32)
    request.session[_STATE_SESSION_KEY] = state
    redirect_uri = get_redirect_uri(request, callback_path)
    return make_auth_url(redirect_uri, state)


def verify_state(request: HttpRequest, returned_state: str) -> bool:
    expected = request.session.get(_STATE_SESSION_KEY)
    return bool(expected and secrets.compare_digest(expected, returned_state))


def exchange_code(code: str, redirect_uri: str) -> dict:
    """Exchange auth code for tokens. Returns token dict or raises ValueError."""
    resp = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_userinfo(access_token: str) -> dict:
    """Fetch identity claims from Google. Returns the raw OIDC userinfo dict
    (at least 'sub', 'email', 'name'; 'picture' when the account has one)."""
    resp = httpx.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def verify_id_token(id_token: str) -> dict:
    """Verifies a Google ID token issued to a **native** client — the
    Flutter staff app's own Google Sign-In (`google_sign_in` package,
    configured with `serverClientId: GOOGLE_CLIENT_ID` so the token it
    gets is audienced for *this* server, the same web client every
    other Google flow here already uses — no separate Android client
    ID needed for verification, only for letting the sign-in itself
    happen on-device, a Google Cloud Console registration step outside
    this code). Distinct from `get_verified_google_user()` above (the
    web's authorization-code redirect flow) — the app performs the
    whole OAuth dance on-device and hands this function only the
    resulting ID token (a signed JWT), which needs its own
    verification path, not a code exchange.

    Uses Google's `tokeninfo` endpoint (https://developers.google.com/
    identity/sign-in/web/backend-auth#calling-the-tokeninfo-endpoint) —
    validates the signature/expiry server-side at Google and returns
    the decoded claims; simpler than a local JWK-verification library
    for this app's request volume (an internal staff tool, not a
    public-scale API), which is exactly the trade-off Google's own
    docs describe that endpoint as appropriate for.

    Returns the same dict shape as `get_verified_google_user()`: sub/
    email/name/picture. Raises `ValueError` if the token is invalid,
    expired, or audienced for a different client (never trust `aud`
    unchecked — that's the whole point of verifying server-side rather
    than trusting whatever the app claims).
    """
    resp = httpx.get(
        "https://oauth2.googleapis.com/tokeninfo", params={"id_token": id_token}, timeout=10,
    )
    if resp.status_code != 200:
        raise ValueError("Invalid or expired Google ID token")
    info = resp.json()
    if info.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise ValueError("Google ID token was not issued for this app")
    if str(info.get("email_verified")).lower() != "true":
        raise ValueError("Google account email is not verified")
    return {
        "sub": info["sub"],
        "email": info["email"],
        "name": info.get("name", ""),
        "picture": info.get("picture", ""),
    }


def get_verified_google_user(request: HttpRequest, callback_path: str) -> dict | None:
    """
    Complete the OAuth callback. Returns dict(sub, email, name, picture) on
    success, None if state mismatch. Raises httpx.HTTPError / ValueError on
    network/API errors. Called from callback views with request.GET
    containing 'code' and 'state'.
    """
    state = request.GET.get("state", "")
    code = request.GET.get("code", "")
    if not verify_state(request, state) or not code:
        return None
    redirect_uri = get_redirect_uri(request, callback_path)
    tokens = exchange_code(code, redirect_uri)
    access_token = tokens.get("access_token", "")
    if not access_token:
        raise ValueError("No access_token in Google response")
    info = get_userinfo(access_token)
    return {
        "sub": info["sub"],
        "email": info["email"],
        "name": info.get("name", ""),
        # OIDC's own field (present on the endpoint this project uses —
        # see this module's own GOOGLE_USERINFO_URL comment for why it's
        # the OIDC endpoint and not the legacy oauth2/v2/userinfo one).
        # A plain hotlinked URL to Google's own CDN, not downloaded/
        # stored locally — good enough for a small staff-facing avatar,
        # not guaranteed permanent if the account's photo changes.
        "picture": info.get("picture", ""),
    }
