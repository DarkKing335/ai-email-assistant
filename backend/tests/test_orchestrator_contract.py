import json
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from src.summarization.models import EmailParticipant, SummarizationRequest
from src.summarization.service import SummarizationService
from conftest import FakeProvider


class FixedOrchestratorEmailSummary(BaseModel):
    """Mirror of the protected orchestrator input contract for compatibility testing."""

    summary_text: str
    sender: str | None = None
    subject: str | None = None
    raw_email: str | None = None


@pytest.mark.asyncio
async def test_result_validates_as_fixed_orchestrator_contract(message_factory, generated_summary):
    older = message_factory(
        "message-old",
        thread_id="thread-1",
        body_text="Earlier private content",
        sent_at=datetime(2026, 7, 15, 8, 0, tzinfo=UTC),
    )
    newer = message_factory(
        "message-1",
        thread_id="thread-1",
        body_text="Latest private content",
        sent_at=datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
    )
    newer.sender = EmailParticipant(name="Latest Customer", address="latest@example.com")
    newer.subject = "Latest customer request"
    primary = FakeProvider("groq", [generated_summary])
    fallback = FakeProvider("gemini", [generated_summary])
    service = SummarizationService(
        primary=primary,
        fallback=fallback,
        retry_delay_seconds=0,
    )

    # Deliberately reverse input order; the newest retained message owns handoff metadata.
    result = await service.summarize(SummarizationRequest(messages=[newer, older]))
    orchestrator_input = FixedOrchestratorEmailSummary.model_validate(result.model_dump())

    assert orchestrator_input.summary_text == generated_summary.summary_text
    assert orchestrator_input.sender == "Latest Customer <latest@example.com>"
    assert orchestrator_input.subject == "Latest customer request"
    assert orchestrator_input.raw_email is None
    serialized_result = json.dumps(result.model_dump(mode="json"))
    assert "Earlier private content" not in serialized_result
    assert "Latest private content" not in serialized_result
