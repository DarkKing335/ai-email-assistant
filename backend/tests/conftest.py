from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from src.summarization.errors import ProviderError
from src.summarization.models import (
    EmailMessageInput,
    EmailParticipant,
    GeneratedSummary,
)


class FakeProvider:
    def __init__(
        self,
        name: str,
        outcomes: Sequence[GeneratedSummary | ProviderError],
    ) -> None:
        self.name = name
        self.model = f"{name}-test-model"
        self.outcomes = list(outcomes)
        self.calls = 0
        self.prompts: list[tuple[str, str]] = []

    async def generate(self, *, system_prompt: str, user_prompt: str) -> GeneratedSummary:
        self.prompts.append((system_prompt, user_prompt))
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, ProviderError):
            raise outcome
        return outcome


@pytest.fixture
def participant() -> EmailParticipant:
    return EmailParticipant(name="Alice", address="alice@example.com")


@pytest.fixture
def message_factory(participant):
    def build(
        message_id: str = "message-1",
        *,
        thread_id: str | None = None,
        body_text: str | None = "Please send the report by Friday.",
        body_html: str | None = None,
        sent_at: datetime | None = None,
    ) -> EmailMessageInput:
        return EmailMessageInput(
            message_id=message_id,
            thread_id=thread_id,
            subject="Quarterly report",
            sender=participant,
            to_recipients=[EmailParticipant(address="bob@example.com")],
            sent_at=sent_at or datetime(2026, 7, 15, 9, 0, tzinfo=UTC),
            body_text=body_text,
            body_html=body_html,
        )

    return build


@pytest.fixture
def generated_summary() -> GeneratedSummary:
    return GeneratedSummary(
        summary_text="Alice asks Bob to send the quarterly report by Friday. The request is pending.",
        key_points=[
            {"text": "The quarterly report is requested.", "source_message_ids": ["message-1"]}
        ],
        action_items=[
            {
                "task": "Send the quarterly report",
                "owner": "Bob",
                "deadline": "Friday",
                "source_message_ids": ["message-1"],
            }
        ],
        language="en",
    )
