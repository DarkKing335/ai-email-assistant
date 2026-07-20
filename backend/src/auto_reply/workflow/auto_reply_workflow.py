"""
auto_reply_workflow.py — Core orchestrator of the AutoReply feature.
"""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.agent.guardrails import (
    GuardrailError,
    sanitize_sender,
)
from src.auto_reply.infrastructure.models import ExecutionStatus
from src.auto_reply.infrastructure.repositories import MatchLogRepository
from src.auto_reply.proxy.gmail_adapter import InboundEmailEvent
from src.auto_reply.proxy.gmail_client import GmailApiError, create_draft, get_message
from src.auto_reply.proxy.google_oauth import OAuthError
from src.auto_reply.proxy.llm_adapter import LLMAdapter
from src.auto_reply.tools.draft_store_tool import DraftStoreTool
from src.auto_reply.tools.matcher_tool import MatcherTool
from src.auto_reply.tools.oauth_store_tool import NotConnectedError, OAuthStoreTool
from src.config import get_settings
from src.orchestrator.orchestrator import EmailOrchestrator
from src.summarization.api import _build_summarization_service
from src.summarization.errors import SummarizationError

logger = logging.getLogger(__name__)


class AutoReplyWorkflow:
    """End-to-end processing pipeline for a single inbound email."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._log_repo = MatchLogRepository(session)
        self._matcher = MatcherTool(session)
        self._draft_store = DraftStoreTool(session)
        
        # Instantiate stateless domain services
        self._llm_adapter = LLMAdapter(
            summarization_service=_build_summarization_service(),
            orchestrator=EmailOrchestrator(),
        )

    async def process_initial(self, event: InboundEmailEvent) -> int | None:
        """Process a new email from the Gmail adapter.
        
        Returns the new MatchLog ID, or None if skipped/invalid.
        """
        start_time = time.monotonic()

        # 1. Sanitize sender
        try:
            sender_email, sender_name = sanitize_sender(event.sender_email)
        except GuardrailError as exc:
            logger.warning(
                "workflow_invalid_sender message_id=%s sender=%s error=%s",
                event.gmail_message_id,
                event.sender_email,
                exc.message,
            )
            return None

        # 2. Idempotency guard
        existing_log = await self._log_repo.get_by_gmail_message_id(event.gmail_message_id)
        if existing_log:
            logger.info("workflow_duplicate_message message_id=%s", event.gmail_message_id)
            return existing_log.id

        # 3. Create initial MatchLog
        match_log = await self._log_repo.create(
            gmail_message_id=event.gmail_message_id,
            gmail_thread_id=event.gmail_thread_id,
            sender_email=sender_email,
            sender_name=sender_name,
            subject=event.subject,
            received_at=event.received_at,
        )

        # 4. Whitelist Match
        match_result = await self._matcher.match(sender_email)
        if not match_result:
            await self._log_repo.update_status(
                match_log,
                status=ExecutionStatus.SKIPPED,
                error_detail="Sender not on whitelist.",
                processing_ms=self._elapsed_ms(start_time),
            )
            return match_log.id

        # Update log with match details
        match_log.whitelist_entry_id = match_result.entry.id
        match_log.matched_rule = match_result.matched_rule
        match_log.status = ExecutionStatus.PROCESSING
        await self._session.flush()

        # 5. Proceed to core logic (which can be retried)
        await self._execute_core(match_log, event, start_time)
        return match_log.id

    async def process_rescan(self, match_log_id: int) -> bool:
        """Re-examine a skipped log against the *current* whitelist.

        Returns True if the email now matches and was processed.

        Whitelist rules are consulted at the instant an email is processed, so
        mail that arrives before its rule exists is filed SKIPPED and stays that
        way — nothing revisits it. That reads as a broken dashboard: you add a
        rule, and mail from that sender still sits in Unmatched.

        The body is not stored on the log — only sender, subject and ids — so
        the message is re-fetched from Gmail rather than reconstructed. That
        also means a rescan needs a connected account and cannot run against
        mail Gmail no longer has.
        """
        start_time = time.monotonic()

        match_log = await self._log_repo.get_by_id(match_log_id)
        if not match_log or match_log.status != ExecutionStatus.SKIPPED:
            # Not an error: a concurrent poll or an earlier rescan in the same
            # sweep may have already moved this log on.
            return False

        match_result = await self._matcher.match(match_log.sender_email)
        if not match_result:
            return False

        event = await self._refetch_event(match_log)
        if event is None:
            return False

        match_log.whitelist_entry_id = match_result.entry.id
        match_log.matched_rule = match_result.matched_rule
        match_log.status = ExecutionStatus.PROCESSING
        # The skip reason is now false — clear it rather than leave it to
        # contradict the row's own status.
        match_log.error_detail = None
        await self._session.flush()

        logger.info(
            "workflow_rescan_matched log=%d sender=%s rule=%s",
            match_log.id,
            match_log.sender_email,
            match_result.matched_rule,
        )
        await self._execute_core(match_log, event, start_time)
        return True

    async def _refetch_event(self, match_log: Any) -> InboundEmailEvent | None:
        """Pull the original message back from Gmail. None if unavailable.

        Every failure is logged and swallowed: a rescan sweeps a batch, and one
        message that Gmail has since deleted must not abort the rest.
        """
        try:
            store = OAuthStoreTool(self._session)
            access_token = await store.get_valid_access_token()
            return await get_message(access_token, match_log.gmail_message_id)
        except NotConnectedError:
            logger.warning("rescan_skipped_not_connected log=%d", match_log.id)
            return None
        except (GmailApiError, OAuthError) as exc:
            logger.warning(
                "rescan_refetch_failed log=%d message_id=%s error=%s",
                match_log.id,
                match_log.gmail_message_id,
                exc.message,
            )
            return None

    async def process_retry(self, match_log_id: int, event: InboundEmailEvent) -> None:
        """Process a retry attempt for an existing log."""
        start_time = time.monotonic()
        match_log = await self._log_repo.get_by_id(match_log_id)
        if not match_log or match_log.status != ExecutionStatus.PROCESSING:
            logger.warning("workflow_invalid_retry log=%d", match_log_id)
            return

        match_log = await self._log_repo.increment_retry(match_log)
        await self._execute_core(match_log, event, start_time)

    async def _execute_core(
        self,
        match_log: Any,
        event: InboundEmailEvent,
        start_time: float,
    ) -> None:
        """Core AI generation and storage logic."""
        try:
            # 1. Summarise + generate draft
            generation = await self._llm_adapter.generate_draft(event)
            draft_result = generation.draft

            # 1b. Persist the summary before anything else can fail.
            #
            # `mode="json"` so datetimes and enums become JSON-native types —
            # the raw model_dump() would put objects the JSON column cannot
            # serialise.
            match_log.summary_json = generation.summary.model_dump(mode="json")

            # 2. Store Draft
            draft = await self._draft_store.store_draft(
                match_log_id=match_log.id,
                draft_text=draft_result.draft_text,
                template_id=draft_result.template_id,
                confidence_score=draft_result.confidence_score,
                extracted_data=draft_result.extracted_data,
                provider_used=draft_result.provider_used,
                used_fallback=draft_result.used_fallback,
            )

            # 2b. File it as a real Gmail draft.
            #
            # After persisting, never before: the generated text is the
            # expensive artefact and must survive Gmail being unreachable. The
            # reverse order would risk an orphan draft in the mailbox with no
            # row pointing at it.
            draft.gmail_draft_id = await self._create_gmail_draft(
                event, draft_result.draft_text
            )

            # 3. Mark Completed
            await self._log_repo.update_status(
                match_log,
                status=ExecutionStatus.COMPLETED,
                error_detail=None,
                processing_ms=self._elapsed_ms(start_time),
            )
            logger.info("workflow_completed log=%d", match_log.id)

        except SummarizationError as exc:
            # Summarization errors are handled gracefully (retryable or fatal)
            if exc.retryable and match_log.retry_count < get_settings().auto_reply_max_retries:
                # Signal to worker to enqueue retry (worker handles Exception bubbling)
                raise
            else:
                await self._log_repo.update_status(
                    match_log,
                    status=ExecutionStatus.FAILED,
                    error_detail=f"Summarization error: {exc.safe_message}",
                    processing_ms=self._elapsed_ms(start_time),
                )
                logger.error("workflow_failed log=%d error=%s", match_log.id, exc.safe_message)

        except Exception as exc:
            # Unexpected errors
            if match_log.retry_count < get_settings().auto_reply_max_retries:
                raise
            else:
                await self._log_repo.update_status(
                    match_log,
                    status=ExecutionStatus.FAILED,
                    error_detail=f"Internal error: {exc!s}",
                    processing_ms=self._elapsed_ms(start_time),
                )
                logger.error("workflow_failed log=%d error=%s", match_log.id, exc, exc_info=True)

    async def _create_gmail_draft(
        self, event: InboundEmailEvent, draft_text: str
    ) -> str | None:
        """File the reply as a Gmail draft. Returns its id, or None on failure.

        Deliberately swallows its errors. The email has already been summarised
        and the reply text stored, so a Gmail outage here should leave a
        completed row with no draft link — not fail the email and drag it
        through the retry queue, re-billing the LLM each time.
        """
        try:
            store = OAuthStoreTool(self._session)
            access_token = await store.get_valid_access_token()
            draft_id = await create_draft(
                access_token, event=event, body_text=draft_text
            )
        except NotConnectedError:
            # Reachable when the account is disconnected mid-run: the email was
            # already buffered from a poll made while it was still connected.
            logger.warning(
                "gmail_draft_skipped_not_connected message_id=%s",
                event.gmail_message_id,
            )
            return None
        except (GmailApiError, OAuthError) as exc:
            logger.error(
                "gmail_draft_failed message_id=%s error=%s",
                event.gmail_message_id,
                exc.message,
            )
            return None

        logger.info(
            "gmail_draft_created message_id=%s draft=%s",
            event.gmail_message_id,
            draft_id,
        )
        return draft_id

    @staticmethod
    def _elapsed_ms(start_time: float) -> int:
        return int((time.monotonic() - start_time) * 1000)
