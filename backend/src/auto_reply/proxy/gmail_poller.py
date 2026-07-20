"""
gmail_poller.py — `GmailAdapterProtocol` implementation backed by the Gmail API.

Satisfies the same interface as `PushModeGmailAdapter`, so the workflow and the
background worker are unchanged — this was the point of defining the protocol.

**Why an internal buffer.** The worker calls `receive()` in a tight loop (it
sleeps 0.5s only when idle). Calling Gmail at that rate would exhaust the API
quota within minutes. So a poll fetches a batch, buffers it, and serves
subsequent `receive()` calls from memory until the interval elapses again.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import UTC, datetime, timedelta

from src.auto_reply.infrastructure.repositories import MatchLogRepository
from src.auto_reply.proxy.gmail_adapter import InboundEmailEvent
from src.auto_reply.proxy.gmail_client import (
    GmailApiError,
    get_message,
    list_message_ids,
    list_sent_thread_ids,
)
from src.auto_reply.proxy.google_oauth import OAuthError
from src.auto_reply.tools.oauth_store_tool import NotConnectedError, OAuthStoreTool
from src.config import get_settings
from src.database import db_session

logger = logging.getLogger(__name__)


class OAuthPollingGmailAdapter:
    """Polls Gmail on an interval and hands messages to the workflow."""

    def __init__(self) -> None:
        self._buffer: deque[InboundEmailEvent] = deque()
        self._next_poll_at: datetime | None = None
        # Serialises polls: `receive()` is only called by the single worker
        # loop today, but a second caller must not start a parallel fetch.
        self._lock = asyncio.Lock()
        self._last_error: str | None = None
        self._is_connected = False

    # -- protocol ----------------------------------------------------------

    async def receive(self) -> InboundEmailEvent | None:
        if self._buffer:
            return self._buffer.popleft()

        now = datetime.now(UTC)
        if self._next_poll_at is not None and now < self._next_poll_at:
            return None

        async with self._lock:
            # Another caller may have refilled the buffer while we waited.
            if self._buffer:
                return self._buffer.popleft()
            await self._poll()

        return self._buffer.popleft() if self._buffer else None

    async def acknowledge(self, gmail_message_id: str) -> None:
        # Nothing to do: the watermark advances on a successful poll, and the
        # workflow's own `gmail_message_id` uniqueness rejects replays.
        return None

    # -- status, for the API ----------------------------------------------

    @property
    def status(self) -> dict:
        return {
            "connected": self._is_connected,
            "buffered": len(self._buffer),
            "next_poll_at": self._next_poll_at.isoformat() if self._next_poll_at else None,
            "last_error": self._last_error,
        }

    # -- internals ---------------------------------------------------------

    def _schedule_next(self, *, seconds: int | None = None) -> None:
        interval = seconds or get_settings().gmail_poll_interval_seconds
        self._next_poll_at = datetime.now(UTC) + timedelta(seconds=interval)

    async def _sweep_replies(
        self, session, access_token: str, since: datetime
    ) -> None:
        """Mark logs whose thread has since been replied on.

        Failures are swallowed. This is bookkeeping that only decides whether an
        already-processed email stays visible; letting it abort the poll would
        stop new mail being fetched, which is far worse than an email lingering
        in the list for one more interval.
        """
        settings = get_settings()
        try:
            thread_ids = await list_sent_thread_ids(
                access_token,
                after=since,
                max_results=settings.gmail_max_results_per_poll,
            )
            if not thread_ids:
                return

            marked = await MatchLogRepository(session).mark_replied(
                thread_ids, replied_at=datetime.now(UTC)
            )
            if marked:
                logger.info("gmail_replies_detected marked=%d", marked)

        except Exception as exc:  # noqa: BLE001 - see docstring
            logger.warning("gmail_reply_sweep_failed: %s", exc)

    async def _poll(self) -> None:
        settings = get_settings()

        try:
            async with db_session() as session:
                store = OAuthStoreTool(session)
                credential = await store.get()

                if credential is None:
                    self._is_connected = False
                    self._last_error = None
                    # Nothing to do until an account is connected; back off hard
                    # rather than re-checking every interval.
                    self._schedule_next(seconds=max(60, settings.gmail_poll_interval_seconds))
                    return

                self._is_connected = True
                access_token = await store.get_valid_access_token()

                since = credential.last_polled_at
                if since is None:
                    # First poll after connecting. A short lookback so linking an
                    # account does not draft replies to a month of history.
                    since = datetime.now(UTC) - timedelta(
                        minutes=settings.gmail_initial_lookback_minutes
                    )
                elif since.tzinfo is None:
                    since = since.replace(tzinfo=UTC)

                # Captured *before* fetching: a message arriving mid-poll is
                # then caught next time rather than falling in the gap.
                poll_started_at = datetime.now(UTC)

                message_ids = await list_message_ids(
                    access_token,
                    query=settings.gmail_poll_query,
                    after=since,
                    max_results=settings.gmail_max_results_per_poll,
                )

                fetched = 0
                for message_id in reversed(message_ids):  # oldest first
                    try:
                        event = await get_message(access_token, message_id)
                    except GmailApiError as exc:
                        # One unreadable message must not stall the batch.
                        logger.warning(
                            "gmail_fetch_failed message_id=%s error=%s", message_id, exc.message
                        )
                        continue
                    self._buffer.append(event)
                    fetched += 1

                # Retire emails that have since been replied to. Runs in the
                # same window as the inbound fetch, so a reply sent between two
                # polls is caught by the next one.
                await self._sweep_replies(session, access_token, since)

                await store.mark_polled(poll_started_at)
                self._last_error = None

                if fetched:
                    logger.info("gmail_poll fetched=%d buffered=%d", fetched, len(self._buffer))

            self._schedule_next()

        except NotConnectedError:
            self._is_connected = False
            self._last_error = None
            self._schedule_next()

        except (GmailApiError, OAuthError) as exc:
            self._last_error = exc.message
            logger.error("gmail_poll_failed: %s", exc.message)
            # Back off on failure so a revoked token or an outage does not
            # generate a request every interval indefinitely.
            retryable = getattr(exc, "retryable", False)
            self._schedule_next(
                seconds=get_settings().gmail_poll_interval_seconds * (2 if retryable else 10)
            )

        except Exception as exc:  # noqa: BLE001 - the worker must never die
            self._last_error = str(exc)
            logger.error("gmail_poll_unexpected_error: %s", exc, exc_info=True)
            self._schedule_next(seconds=get_settings().gmail_poll_interval_seconds * 5)


_poller: OAuthPollingGmailAdapter | None = None


def get_gmail_poller() -> OAuthPollingGmailAdapter:
    global _poller
    if _poller is None:
        _poller = OAuthPollingGmailAdapter()
    return _poller
