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
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

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
    """Fetch email, name, sub from Google. Returns dict with 'sub', 'email', 'name'."""
    resp = httpx.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_verified_google_user(request: HttpRequest, callback_path: str) -> dict | None:
    """
    Complete the OAuth callback. Returns dict(sub, email, name) on success,
    None if state mismatch. Raises httpx.HTTPError / ValueError on network/API errors.
    Called from callback views with request.GET containing 'code' and 'state'.
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
    }
