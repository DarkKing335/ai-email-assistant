"""
google_oauth.py — OAuth 2.0 authorization-code flow for Google.

Implemented directly against Google's endpoints with `httpx` rather than
`google-auth-oauthlib`. The flow is three requests and the SDK would pull in a
substantial dependency tree to save perhaps eighty lines — and hide the parts
worth being explicit about (offline access, the once-only refresh token).

Reference: https://developers.google.com/identity/protocols/oauth2/web-server
"""
from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

_HTTP_TIMEOUT = 30.0


class OAuthError(RuntimeError):
    """OAuth failed in a way the user needs to be told about."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable


class OAuthNotConfigured(OAuthError):
    def __init__(self) -> None:
        super().__init__(
            "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET in backend/.env — see docs/setup/gmail-oauth.md."
        )


@dataclass
class TokenBundle:
    access_token: str
    #: Absent on refresh — Google issues one only at first consent.
    refresh_token: str | None
    expires_at: datetime
    scopes: str


# ---------------------------------------------------------------------------
# CSRF state
# ---------------------------------------------------------------------------
#
# Held in memory: the value lives for the few seconds between redirecting to
# Google and Google redirecting back, and it is only ever read by the same
# process that wrote it. Persisting it would outlive its own usefulness.

_pending_states: dict[str, float] = {}
_STATE_TTL_SECONDS = 600


def issue_state() -> str:
    _prune_states()
    state = secrets.token_urlsafe(32)
    _pending_states[state] = time.monotonic()
    return state


def consume_state(state: str) -> bool:
    """Validate and burn a state value. False if unknown or expired."""
    _prune_states()
    return _pending_states.pop(state, None) is not None


def _prune_states() -> None:
    now = time.monotonic()
    for key, created in list(_pending_states.items()):
        if now - created > _STATE_TTL_SECONDS:
            del _pending_states[key]


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------


def build_authorization_url(state: str) -> str:
    settings = get_settings()
    if not settings.has_google_oauth:
        raise OAuthNotConfigured()

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": settings.google_oauth_scopes,
        # Required for a refresh token — without it access dies in an hour and
        # the user has to re-consent constantly.
        "access_type": "offline",
        # Google returns a refresh token only on the *first* consent for a
        # client/account pair. Forcing the prompt means reconnecting after the
        # database is wiped still yields one, rather than silently succeeding
        # with no way to refresh.
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


async def exchange_code(code: str) -> TokenBundle:
    settings = get_settings()
    if not settings.has_google_oauth:
        raise OAuthNotConfigured()

    payload = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret.get_secret_value(),
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }
    data = await _post_token(payload, action="exchange authorization code")

    refresh_token = data.get("refresh_token")
    if not refresh_token:
        # Without this the connection works for an hour and then dies in a way
        # that looks unrelated, so fail loudly now.
        raise OAuthError(
            "Google did not return a refresh token. Revoke this app's access at "
            "https://myaccount.google.com/permissions and connect again."
        )

    return TokenBundle(
        access_token=data["access_token"],
        refresh_token=refresh_token,
        expires_at=_expiry_from(data),
        scopes=data.get("scope", settings.google_oauth_scopes),
    )


async def refresh_access_token(refresh_token: str) -> TokenBundle:
    settings = get_settings()
    if not settings.has_google_oauth:
        raise OAuthNotConfigured()

    payload = {
        "refresh_token": refresh_token,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret.get_secret_value(),
        "grant_type": "refresh_token",
    }
    data = await _post_token(payload, action="refresh access token")

    return TokenBundle(
        access_token=data["access_token"],
        # Not re-issued on refresh; the caller keeps the one it has.
        refresh_token=data.get("refresh_token"),
        expires_at=_expiry_from(data),
        scopes=data.get("scope", settings.google_oauth_scopes),
    )


async def fetch_account_email(access_token: str) -> str:
    """Which account was connected — shown in the UI so it is unambiguous."""
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        response = await client.get(
            USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code != 200:
        raise OAuthError(
            f"Could not read the Google account profile (HTTP {response.status_code}).",
            retryable=True,
        )
    email = response.json().get("email")
    if not email:
        raise OAuthError("Google did not return an email address for the account.")
    return str(email)


async def revoke_token(token: str) -> None:
    """Best-effort revocation. Local disconnect proceeds regardless."""
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            await client.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.HTTPError as exc:
        logger.warning("token revocation failed (continuing): %s", exc)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


async def _post_token(payload: dict[str, str], *, action: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(TOKEN_ENDPOINT, data=payload)
    except httpx.HTTPError as exc:
        raise OAuthError(f"Could not reach Google to {action}: {exc}", retryable=True) from exc

    if response.status_code != 200:
        detail = _describe_token_error(response)
        raise OAuthError(
            f"Google refused to {action}: {detail}",
            # 5xx is Google's problem and worth retrying; 4xx is ours.
            retryable=response.status_code >= 500,
        )
    return response.json()


def _describe_token_error(response: httpx.Response) -> str:
    """Translate Google's terser error codes into something actionable."""
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"

    code = body.get("error", "unknown_error")
    description = body.get("error_description", "")

    hints = {
        "redirect_uri_mismatch": (
            "the redirect URI does not match the one registered on the OAuth "
            "client — they must be identical, including port and trailing path"
        ),
        "invalid_client": "the client ID or secret is wrong",
        "invalid_grant": (
            "the code or refresh token is expired, already used, or was revoked — "
            "connect the account again"
        ),
        "access_denied": "consent was declined",
    }
    hint = hints.get(code)
    parts = [p for p in (code, description, hint) if p]
    return " — ".join(parts)


def _expiry_from(data: dict) -> datetime:
    # 60s of headroom so a token cannot expire mid-request.
    expires_in = int(data.get("expires_in", 3600))
    return datetime.now(UTC) + timedelta(seconds=max(0, expires_in - 60))
