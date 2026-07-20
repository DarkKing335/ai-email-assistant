"""
oauth_store_tool.py — Persistence and refresh for the connected Google account.

The only place OAuth tokens are read or written. Everything else asks for a
valid access token and gets one, refreshed transparently if needed.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.infrastructure.models import OAuthCredential
from src.auto_reply.proxy.google_oauth import (
    OAuthError,
    TokenBundle,
    refresh_access_token,
    revoke_token,
)

logger = logging.getLogger(__name__)

PROVIDER_GOOGLE = "google"


class NotConnectedError(OAuthError):
    def __init__(self) -> None:
        super().__init__("No Google account is connected.")


class OAuthStoreTool:
    """Read/write the single connected account."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> OAuthCredential | None:
        result = await self._session.execute(
            select(OAuthCredential).where(OAuthCredential.provider == PROVIDER_GOOGLE)
        )
        return result.scalar_one_or_none()

    async def save(self, *, email_address: str, tokens: TokenBundle) -> OAuthCredential:
        """Create or replace the stored credential."""
        if tokens.refresh_token is None:
            raise OAuthError("Cannot store a credential without a refresh token.")

        existing = await self.get()
        if existing:
            existing.email_address = email_address
            existing.access_token = tokens.access_token
            existing.refresh_token = tokens.refresh_token
            existing.token_expiry = tokens.expires_at
            existing.scopes = tokens.scopes
            # Reconnecting starts a fresh watermark — the lookback window
            # applies again rather than replaying everything since the last poll.
            existing.last_polled_at = None
            await self._session.flush()
            logger.info("oauth credential replaced for %s", email_address)
            return existing

        credential = OAuthCredential(
            provider=PROVIDER_GOOGLE,
            email_address=email_address,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_expiry=tokens.expires_at,
            scopes=tokens.scopes,
        )
        self._session.add(credential)
        await self._session.flush()
        logger.info("oauth credential stored for %s", email_address)
        return credential

    async def get_valid_access_token(self) -> str:
        """Return a usable access token, refreshing it if it has expired."""
        credential = await self.get()
        if credential is None:
            raise NotConnectedError()

        expiry = credential.token_expiry
        # SQLite hands back naive datetimes; compare like with like.
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)

        if expiry > datetime.now(UTC):
            return credential.access_token

        logger.info("access token expired, refreshing for %s", credential.email_address)
        tokens = await refresh_access_token(credential.refresh_token)

        credential.access_token = tokens.access_token
        credential.token_expiry = tokens.expires_at
        # Google does not re-issue the refresh token on refresh; keep the
        # existing one rather than overwriting it with None.
        if tokens.refresh_token:
            credential.refresh_token = tokens.refresh_token
        await self._session.flush()

        return credential.access_token

    async def mark_polled(self, polled_at: datetime) -> None:
        credential = await self.get()
        if credential:
            credential.last_polled_at = polled_at
            await self._session.flush()

    async def disconnect(self) -> bool:
        """Revoke with Google and delete locally. False if nothing was connected."""
        credential = await self.get()
        if credential is None:
            return False

        # Revocation is best-effort: if Google is unreachable the local
        # credential must still go, or the UI would claim it is still connected.
        await revoke_token(credential.refresh_token)

        await self._session.execute(
            delete(OAuthCredential).where(OAuthCredential.provider == PROVIDER_GOOGLE)
        )
        await self._session.flush()
        logger.info("oauth credential removed for %s", credential.email_address)
        return True
