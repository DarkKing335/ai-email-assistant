from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.summarization.models import SummarizationRequest


def test_multiple_messages_must_share_a_thread(message_factory):
    with pytest.raises(ValidationError):
        SummarizationRequest(
            messages=[
                message_factory("one", thread_id="thread-a"),
                message_factory("two", thread_id="thread-b"),
            ]
        )


def test_message_ids_must_be_unique(message_factory):
    with pytest.raises(ValidationError):
        SummarizationRequest(
            messages=[
                message_factory("same", thread_id="thread-a"),
                message_factory(
                    "same",
                    thread_id="thread-a",
                    sent_at=datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
                ),
            ]
        )


def test_message_requires_readable_body(message_factory):
    with pytest.raises(ValidationError):
        message_factory(body_text=" ", body_html="")


def test_timestamp_must_have_timezone(message_factory):
    with pytest.raises(ValidationError):
        message_factory(sent_at=datetime(2026, 7, 15, 9, 0))
