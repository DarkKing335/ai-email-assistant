"""
llm_adapter.py — Thin adapter that wraps the existing EmailOrchestrator.

The AutoReply workflow calls `generate_draft()` to get a reply draft.
This adapter:
  1. Reuses `SummarizationService` (existing) to summarise the email thread.
  2. Passes the result to `EmailOrchestrator` (existing) to select a template
     and render the draft.

No existing orchestrator code is modified.
"""
from __future__ import annotations

import logging

from src.auto_reply.proxy.gmail_adapter import InboundEmailEvent
from src.orchestrator.contracts import DraftResult
from src.orchestrator.orchestrator import EmailOrchestrator
from src.summarization.models import (
    EmailMessageInput,
    EmailParticipant,
    SummarizationRequest,
    SummarizationResult,
)
from src.summarization.service import SummarizationService

logger = logging.getLogger(__name__)


class LLMAdapter:
    """Coordinate summarization → orchestration to produce a draft reply."""

    def __init__(
        self,
        summarization_service: SummarizationService,
        orchestrator: EmailOrchestrator,
    ) -> None:
        self._summarizer = summarization_service
        self._orchestrator = orchestrator

    async def generate_draft(self, event: InboundEmailEvent) -> DraftResult:
        """Summarise `event` and generate a draft reply.

        Parameters
        ----------
        event:
            The inbound email event from the Gmail adapter.
        """
        # Build SummarizationRequest from the inbound event
        request = self._build_summarization_request(event)

        # Summarize (async, uses existing SummarizationService)
        summary: SummarizationResult = await self._summarizer.summarize(
            request, request_id=event.gmail_message_id
        )

        # Route + draft
        draft: DraftResult = self._orchestrator.run(summary)

        logger.info(
            "llm_adapter_draft_generated message_id=%s template=%s provider=%s fallback=%s",
            event.gmail_message_id,
            draft.template_id,
            draft.provider_used,
            draft.used_fallback,
        )
        return draft

    @staticmethod
    def _build_summarization_request(event: InboundEmailEvent) -> SummarizationRequest:
        """Convert an InboundEmailEvent into a SummarizationRequest."""
        body_text = event.body_text
        body_html = event.body_html

        message = EmailMessageInput(
            message_id=event.gmail_message_id,
            thread_id=event.gmail_thread_id,
            subject=event.subject or "(no subject)",
            sender=EmailParticipant(
                address=event.sender_email,
                name=event.sender_name,
            ),
            sent_at=event.received_at,
            body_text=body_text if body_text and body_text.strip() else None,
            body_html=body_html,
        )

        return SummarizationRequest(messages=[message])
