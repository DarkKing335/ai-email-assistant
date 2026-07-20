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

import asyncio
import logging
from dataclasses import dataclass

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


@dataclass
class DraftGeneration:
    """Both halves of the pipeline's output.

    The summary used to be a local variable that went out of scope the moment
    the draft was returned — every whitelisted email paid for that LLM call and
    then threw the result away. Returning it here lets the workflow persist it,
    which is what the Inbox view reads.

    Kept separate from `DraftResult` on purpose: that is the orchestrator's
    contract, and the summary is an *input* to routing, not the orchestrator's
    output.
    """

    draft: DraftResult
    summary: SummarizationResult


class LLMAdapter:
    """Coordinate summarization → orchestration to produce a draft reply."""

    def __init__(
        self,
        summarization_service: SummarizationService,
        orchestrator: EmailOrchestrator,
    ) -> None:
        self._summarizer = summarization_service
        self._orchestrator = orchestrator

    async def generate_draft(self, event: InboundEmailEvent) -> DraftGeneration:
        """Summarise `event` and generate a draft reply.

        Returns both the draft and the summary it was built from, so the caller
        can persist the summary rather than discard it.

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

        # Route + draft.
        #
        # `run()` is synchronous and now makes *two* blocking LLM calls (routing,
        # then drafting). Called directly it would block the event loop for
        # several seconds — freezing the background worker and every API request
        # the panel makes, since they share one loop. Off to a thread it goes.
        draft: DraftResult = await asyncio.to_thread(self._orchestrator.run, summary)

        logger.info(
            "llm_adapter_draft_generated message_id=%s template=%s provider=%s fallback=%s",
            event.gmail_message_id,
            draft.template_id,
            draft.provider_used,
            draft.used_fallback,
        )
        return DraftGeneration(draft=draft, summary=summary)

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
