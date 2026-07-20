"""
gmail_auth_router.py — Connect and disconnect a Google account.

The OAuth flow lives on the backend, not in the extension: the backend is what
polls Gmail and will create drafts, so it is what needs the tokens. The
extension only ever reads connection *status*.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.proxy.gmail_poller import get_gmail_poller
from src.auto_reply.proxy.google_oauth import (
    OAuthError,
    OAuthNotConfigured,
    build_authorization_url,
    consume_state,
    exchange_code,
    fetch_account_email,
    issue_state,
)
from src.auto_reply.tools.oauth_store_tool import OAuthStoreTool
from src.config import get_settings
from src.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/gmail/auth", tags=["gmail-auth"])


@router.get("/start")
async def start_authorization() -> RedirectResponse:
    """Send the browser to Google's consent screen.

    Opened in a normal tab, not from the extension — the redirect back from
    Google has to land on the backend, and the panel cannot host that.
    """
    try:
        url = build_authorization_url(issue_state())
    except OAuthNotConfigured as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc

    return RedirectResponse(url, status_code=307)


@router.get("/callback", response_class=HTMLResponse)
async def oauth_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Where Google sends the browser back.

    Renders a plain HTML page rather than JSON: a person is looking at this tab,
    not a program.
    """
    if error:
        return _page(
            ok=False,
            title="Connection cancelled",
            detail=f"Google reported: {error}",
        )

    if not code or not state:
        return _page(
            ok=False,
            title="Invalid callback",
            detail="Google's response was missing the authorization code.",
        )

    # The state proves this callback belongs to a flow this server started,
    # rather than a link someone else crafted.
    if not consume_state(state):
        return _page(
            ok=False,
            title="Expired or invalid request",
            detail=(
                "This authorization link is no longer valid. Start the "
                "connection again from the extension's settings."
            ),
        )

    try:
        tokens = await exchange_code(code)
        email = await fetch_account_email(tokens.access_token)
        await OAuthStoreTool(db).save(email_address=email, tokens=tokens)
    except OAuthError as exc:
        logger.error("oauth callback failed: %s", exc.message)
        return _page(ok=False, title="Could not connect", detail=exc.message)

    logger.info("gmail connected for %s", email)
    return _page(
        ok=True,
        title="Gmail connected",
        detail=(
            f"{email} is now connected. New mail will be checked automatically. "
            "You can close this tab."
        ),
    )


@router.get("/status")
async def connection_status(db: AsyncSession = Depends(get_db)) -> dict:
    """What the Settings panel renders."""
    settings = get_settings()
    credential = await OAuthStoreTool(db).get()
    poller = get_gmail_poller()

    return {
        "configured": settings.has_google_oauth,
        "connected": credential is not None,
        "email_address": credential.email_address if credential else None,
        "scopes": credential.scopes.split() if credential else [],
        "last_polled_at": (
            credential.last_polled_at.isoformat()
            if credential and credential.last_polled_at
            else None
        ),
        "poll_interval_seconds": settings.gmail_poll_interval_seconds,
        "poller": poller.status,
    }


@router.delete("/", status_code=204)
async def disconnect(db: AsyncSession = Depends(get_db)) -> None:
    """Revoke with Google and forget the tokens locally."""
    removed = await OAuthStoreTool(db).disconnect()
    if not removed:
        raise HTTPException(status_code=404, detail="No Google account is connected.")


# ---------------------------------------------------------------------------
# Result page
# ---------------------------------------------------------------------------


def _page(*, ok: bool, title: str, detail: str) -> HTMLResponse:
    accent = "#059669" if ok else "#dc2626"
    symbol = "✓" if ok else "!"
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ margin:0; min-height:100vh; display:grid; place-items:center;
           background:#f8fafc; color:#0f172a;
           font-family:system-ui,-apple-system,"Segoe UI",sans-serif; }}
    .card {{ max-width:26rem; padding:2rem; background:#fff; border-radius:.75rem;
             border:1px solid #e2e8f0; text-align:center; }}
    .mark {{ width:2.5rem; height:2.5rem; margin:0 auto 1rem; border-radius:50%;
             display:grid; place-items:center; font-weight:700; color:#fff;
             background:{accent}; }}
    h1 {{ font-size:1.05rem; margin:0 0 .5rem; }}
    p  {{ font-size:.85rem; line-height:1.6; color:#475569; margin:0; }}
    @media (prefers-color-scheme: dark) {{
      body {{ background:#020617; color:#f1f5f9; }}
      .card {{ background:#0f172a; border-color:#1e293b; }}
      p {{ color:#94a3b8; }}
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="mark">{symbol}</div>
    <h1>{title}</h1>
    <p>{detail}</p>
  </div>
</body>
</html>""",
        status_code=200 if ok else 400,
    )
