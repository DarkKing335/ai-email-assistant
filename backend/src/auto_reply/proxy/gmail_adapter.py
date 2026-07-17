"""
gmail_adapter.py — Gmail integration proxy.

Architecture decision
---------------------
Full Gmail OAuth polling is deferred. The *push-mode* adapter exposes
an internal queue that is populated by the `POST /api/v1/gmail/incoming`
endpoint (the Chrome Extension pushes inbound email payloads).

The `GmailAdapterProtocol` defines the interface so a future
`OAuthPollingGmailAdapter` can be swapped in without touching the
workflow layer.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared data class for a received email event
# ---------------------------------------------------------------------------


@dataclass
class InboundEmailEvent:
    """Normalised representation of an inbound email received from any source."""

    gmail_message_id: str
    gmail_thread_id: str | None
    sender_email: str
    sender_name: str | None
    subject: str | None
    body_text: str | None
    body_html: str | None
    received_at: datetime
    to_recipients: list[str] = field(default_factory=list)
    cc_recipients: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Protocol (interface) that all Gmail adapter implementations must satisfy
# ---------------------------------------------------------------------------


class GmailAdapterProtocol(Protocol):
    async def receive(self) -> InboundEmailEvent | None:
        """Return the next available email event, or ``None`` if the queue is empty."""
        ...

    async def acknowledge(self, gmail_message_id: str) -> None:
        """Mark the message as processed (no-op for push mode)."""
        ...


# ---------------------------------------------------------------------------
# Push-mode adapter (default implementation)
# ---------------------------------------------------------------------------


class PushModeGmailAdapter:
    """Receives emails pushed by the Chrome Extension via REST.

    The `gmail_router` calls `enqueue()` when a new email arrives.
    The `BackgroundWorker` calls `receive()` to drain the queue.

    This is a singleton-style object; one instance is shared by the
    FastAPI app's lifespan context.
    """

    def __init__(self, maxsize: int = 500) -> None:
        self._queue: asyncio.Queue[InboundEmailEvent] = asyncio.Queue(maxsize=maxsize)
        self._processed: set[str] = set()

    async def enqueue(self, event: InboundEmailEvent) -> bool:
        """Add an event to the queue.

        Returns ``False`` if the message was already processed (idempotency guard)
        or if the queue is full.
        """
        if event.gmail_message_id in self._processed:
            logger.debug(
                "gmail_adapter_duplicate message_id=%s", event.gmail_message_id
            )
            return False

        try:
            self._queue.put_nowait(event)
            logger.info(
                "gmail_adapter_enqueued message_id=%s sender=%s queue_size=%d",
                event.gmail_message_id,
                event.sender_email,
                self._queue.qsize(),
            )
            return True
        except asyncio.QueueFull:
            logger.warning(
                "gmail_adapter_queue_full message_id=%s dropped", event.gmail_message_id
            )
            return False

    async def receive(self) -> InboundEmailEvent | None:
        """Non-blocking dequeue. Returns ``None`` if the queue is empty."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def acknowledge(self, gmail_message_id: str) -> None:
        self._processed.add(gmail_message_id)
        self._queue.task_done()

    def queue_size(self) -> int:
        return self._queue.qsize()


# ---------------------------------------------------------------------------
# Module-level singleton (shared across the app lifetime)
# ---------------------------------------------------------------------------

_adapter: PushModeGmailAdapter | None = None


def get_gmail_adapter() -> PushModeGmailAdapter:
    global _adapter
    if _adapter is None:
        _adapter = PushModeGmailAdapter()
    return _adapter
