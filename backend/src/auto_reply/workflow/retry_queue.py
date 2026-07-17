"""
retry_queue.py — In-memory async queue for delayed retries.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from src.auto_reply.proxy.gmail_adapter import InboundEmailEvent

logger = logging.getLogger(__name__)


@dataclass
class RetryEvent:
    event: InboundEmailEvent
    match_log_id: int
    attempt_count: int
    execute_after: datetime


class RetryQueue:
    """Manages delayed retries for transient failures."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[RetryEvent] = asyncio.Queue()

    async def enqueue(self, retry_event: RetryEvent) -> None:
        await self._queue.put(retry_event)
        logger.info(
            "retry_enqueued log=%d attempt=%d execute_after=%s",
            retry_event.match_log_id,
            retry_event.attempt_count,
            retry_event.execute_after.isoformat(),
        )

    async def receive(self) -> RetryEvent | None:
        """Returns a ready RetryEvent (execute_after <= now), or None."""
        if self._queue.empty():
            return None

        # Peek without removing
        # Not thread-safe for multiple consumers, but we only have one background worker
        retry_event = self._queue._queue[0]  # type: ignore

        if retry_event.execute_after <= datetime.now(UTC):
            return self._queue.get_nowait()

        return None

    def task_done(self) -> None:
        self._queue.task_done()
