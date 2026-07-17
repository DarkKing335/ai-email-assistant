"""
background_worker.py — Asyncio background tasks for polling and processing.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from src.auto_reply.proxy.gmail_adapter import InboundEmailEvent, get_gmail_adapter
from src.auto_reply.workflow.auto_reply_workflow import AutoReplyWorkflow
from src.auto_reply.workflow.retry_queue import RetryEvent, RetryQueue
from src.config import get_settings
from src.database import db_session

logger = logging.getLogger(__name__)

# Global instances for the lifespan of the app
_retry_queue = RetryQueue()
_worker_tasks: set[asyncio.Task] = set()


async def start_workers() -> None:
    """Start the background worker tasks."""
    task = asyncio.create_task(_worker_loop(), name="auto_reply_worker")
    _worker_tasks.add(task)
    logger.info("background_worker started")


async def stop_workers() -> None:
    """Cancel background workers."""
    for task in _worker_tasks:
        task.cancel()
    if _worker_tasks:
        await asyncio.gather(*_worker_tasks, return_exceptions=True)
    _worker_tasks.clear()
    logger.info("background_worker stopped")


async def _worker_loop() -> None:
    """Continuous polling loop for inbound emails and retries."""
    gmail_adapter = get_gmail_adapter()
    
    while True:
        try:
            processed_work = False

            # 1. Process retries first
            retry_event = await _retry_queue.receive()
            if retry_event:
                processed_work = True
                await _handle_retry(retry_event)
                _retry_queue.task_done()

            # 2. Process new inbound emails
            inbound_event = await gmail_adapter.receive()
            if inbound_event:
                processed_work = True
                await _handle_inbound(inbound_event)
                await gmail_adapter.acknowledge(inbound_event.gmail_message_id)

            # 3. Idle if no work
            if not processed_work:
                await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("background_worker loop error: %s", exc, exc_info=True)
            await asyncio.sleep(1.0)


async def _handle_inbound(event: InboundEmailEvent) -> None:
    """Process a new email event in a dedicated DB session."""
    delay = get_settings().auto_reply_workflow_delay_seconds
    if delay > 0:
        await asyncio.sleep(delay)

    try:
        async with db_session() as session:
            workflow = AutoReplyWorkflow(session)
            # workflow.process_initial might raise an exception if a transient error occurs
            # during _execute_core (e.g. LLM failure) and max retries is not reached.
            match_log_id = await workflow.process_initial(event)
            
    except Exception as exc:
        # Transient failure bubble-up from process_initial
        # We need to extract the match_log_id to enqueue a retry.
        # This requires fetching it by gmail_message_id.
        logger.warning("workflow transient failure on initial process: %s", exc)
        try:
            async with db_session() as session:
                repo = src.auto_reply.infrastructure.repositories.MatchLogRepository(session)
                log = await repo.get_by_gmail_message_id(event.gmail_message_id)
                if log:
                    await _enqueue_retry(event, log.id, 0)
        except Exception as inner_exc:
            logger.error("failed to enqueue retry for initial process: %s", inner_exc)


async def _handle_retry(retry_event: RetryEvent) -> None:
    """Process a retry event in a dedicated DB session."""
    try:
        async with db_session() as session:
            workflow = AutoReplyWorkflow(session)
            await workflow.process_retry(retry_event.match_log_id, retry_event.event)
    except Exception as exc:
        logger.warning("workflow transient failure on retry: %s", exc)
        await _enqueue_retry(retry_event.event, retry_event.match_log_id, retry_event.attempt_count)


async def _enqueue_retry(event: InboundEmailEvent, match_log_id: int, current_attempt: int) -> None:
    """Calculate backoff and enqueue a retry event."""
    settings = get_settings()
    next_attempt = current_attempt + 1
    
    if next_attempt > settings.auto_reply_max_retries:
        logger.error("max retries exceeded for log=%d, dropping", match_log_id)
        return

    # Exponential backoff: base * (2 ^ (attempt - 1))
    delay_seconds = settings.auto_reply_retry_delay_seconds * (2 ** (next_attempt - 1))
    execute_after = datetime.now(UTC) + timedelta(seconds=delay_seconds)

    await _retry_queue.enqueue(
        RetryEvent(
            event=event,
            match_log_id=match_log_id,
            attempt_count=next_attempt,
            execute_after=execute_after,
        )
    )

import src.auto_reply.infrastructure.repositories
